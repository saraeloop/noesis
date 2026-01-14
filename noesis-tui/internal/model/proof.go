package model

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"
	"noesis.dev/tui/internal/ui/proof"

	"github.com/charmbracelet/bubbles/help"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/progress"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// ProofModel renders the Proof screen for a single episode.
type ProofModel struct {
	episodeID string
	proof     *proof.Proof
	diff      *cli.WorkspaceDiff
	loading   bool

	viewport  viewport.Model
	list      list.Model
	spinner   spinner.Model
	progress  progress.Model
	help      help.Model
	keyMap    proofKeyMap
	tabIndex  int
	fullProof bool
	client    *cli.Client
	width     int
	height    int
	header    string
	footer    string
}

// NewProofModel creates a new Proof model.
func NewProofModel(client *cli.Client, episodeID string) *ProofModel {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	pbar := progress.New(progress.WithDefaultGradient())

	delegate := list.NewDefaultDelegate()
	delegate.SetSpacing(0)
	delegate.Styles.SelectedTitle = delegate.Styles.NormalTitle
	delegate.Styles.SelectedDesc = delegate.Styles.NormalDesc

	l := list.New([]list.Item{}, delegate, 0, 0)
	l.SetShowTitle(false)
	l.SetShowStatusBar(false)
	l.SetShowFilter(false)
	l.SetFilteringEnabled(false)
	l.SetShowHelp(false)
	l.SetShowPagination(false)
	l.KeyMap.Quit.Unbind()

	h := help.New()
	h.ShowAll = false

	return &ProofModel{
		episodeID: episodeID,
		loading:   true,
		spinner:   s,
		progress:  pbar,
		client:    client,
		list:      l,
		help:      h,
		keyMap:    newProofKeyMap(),
	}
}

// Init implements tea.Model.
func (p *ProofModel) Init() tea.Cmd {
	return tea.Batch(
		p.spinner.Tick,
		p.fetchProof(),
	)
}

// Update implements tea.Model.
func (p *ProofModel) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case tea.WindowSizeMsg:
		p.width = m.Width
		p.height = m.Height
		p.reflow()
		return p, nil

	case msg.ProofLoaded:
		p.loading = false
		p.proof = m.Proof
		p.diff = m.WorkspaceDiff
		p.setAssertionItems()
		p.reflow()
		return p, nil

	case msg.Error:
		p.loading = false
		return p, nil

	case tea.KeyMsg:
		switch m.String() {
		case "1":
			p.tabIndex = 0
			p.reflow()
			return p, nil
		case "2":
			p.tabIndex = 1
			p.reflow()
			return p, nil
		case "3":
			p.tabIndex = 2
			p.reflow()
			return p, nil
		case "tab", "right":
			p.tabIndex = (p.tabIndex + 1) % 3
			p.reflow()
			return p, nil
		case "shift+tab", "left":
			p.tabIndex--
			if p.tabIndex < 0 {
				p.tabIndex = 2
			}
			p.reflow()
			return p, nil
		case "p":
			p.fullProof = !p.fullProof
			p.reflow()
			return p, nil
		case "d":
			return p, nil
		case "a":
			return p, nil
		}
	}

	var cmd tea.Cmd
	p.spinner, cmd = p.spinner.Update(m)

	if !p.loading {
		p.viewport, _ = p.viewport.Update(m)
	}

	return p, cmd
}

// View implements tea.Model.
func (p *ProofModel) View() string {
	if p.loading {
		return p.viewLoading()
	}
	if p.proof == nil {
		return style.ErrorText.Render("No proof data")
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		p.header,
		p.viewport.View(),
		p.footer,
	)
}

// SetSize sets the window size.
func (p *ProofModel) SetSize(width, height int) {
	p.width = width
	p.height = height
}

func (p *ProofModel) viewLoading() string {
	content := lipgloss.JoinVertical(lipgloss.Center,
		p.spinner.View(),
		style.MutedText.Render("Loading proof..."),
	)
	return lipgloss.Place(p.width, p.height, lipgloss.Center, lipgloss.Center, content)
}

func (p *ProofModel) renderHeader(width int) string {
	tabs := p.renderTabs()
	runLine := style.MutedText.Render(fmt.Sprintf("Run: %s • Task: %s", shortenEpisodeID(p.proof.EpisodeID), p.taskLabel()))
	return lipgloss.JoinVertical(lipgloss.Left, tabs, runLine)
}

func (p *ProofModel) renderPanels(width int) string {
	if p.proof == nil {
		return ""
	}

	switch p.tabIndex {
	case 0:
		return p.renderOverview(width)
	case 1:
		return p.renderTools(width)
	default:
		if p.fullProof {
			return p.renderFullProof(width)
		}
		return p.renderProofSummary(width)
	}
}

func (p *ProofModel) renderGovernancePanel(width int) string {
	status := governanceStyle(p.proof.Governance).Render("[" + p.proof.Governance + "]")
	policy := "Policy"
	if p.proof.PolicyBreach != nil {
		policy = *p.proof.PolicyBreach
	}

	lines := []string{
		fmt.Sprintf("Status       %s", status),
		fmt.Sprintf("Policy       %s", style.MutedText.Render(policy)),
	}

	violations := p.governanceViolations()
	if len(violations) > 0 {
		lines = append(lines, "")
		lines = append(lines, style.ErrorText.Render("Violations:"))
		for _, violation := range violations {
			lines = append(lines, style.ErrorText.Render("• "+violation))
		}
	}

	body := lipgloss.JoinVertical(lipgloss.Left, lines...)
	return renderStatusPanel("Governance", body, width, p.proof.Governance)
}

func (p *ProofModel) renderAssertions(width int) string {
	if len(p.proof.Assertions) == 0 {
		return style.MutedText.Render("No assertions provided.")
	}

	if len(p.proof.Assertions) > 5 {
		listWidth := width - 6
		if listWidth < 20 {
			listWidth = 20
		}
		p.list.SetSize(listWidth, len(p.proof.Assertions))
		return p.list.View()
	}

	lines := make([]string, 0, len(p.proof.Assertions))
	for _, assertion := range p.proof.Assertions {
		lines = append(lines, renderAssertionLine(assertion))
	}
	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (p *ProofModel) renderDiffLines() string {
	if p.proof.Evidence != proof.EvidenceCaptured {
		return ""
	}

	if p.diff == nil {
		return ""
	}

	iconSet := style.Icons()
	var lines []string
	for _, file := range p.diff.Added {
		lines = append(lines, style.SuccessText.Render(fmt.Sprintf("%s %s", iconSet.FileAdded(), file)))
	}
	for _, file := range p.diff.Modified {
		lines = append(lines, style.WarningText.Render(fmt.Sprintf("%s %s", iconSet.FileModified(), file)))
	}
	for _, file := range p.diff.Deleted {
		lines = append(lines, style.ErrorText.Render(fmt.Sprintf("%s %s", iconSet.FileDeleted(), file)))
	}

	if len(lines) == 0 {
		return style.MutedText.Render("No workspace changes detected.")
	}

	return lipgloss.JoinVertical(lipgloss.Left, lines...)
}

func (p *ProofModel) setAssertionItems() {
	if p.proof == nil {
		return
	}
	items := make([]list.Item, 0, len(p.proof.Assertions))
	for _, assertion := range p.proof.Assertions {
		items = append(items, assertionItem{
			title:       renderAssertionLine(assertion),
			description: renderAssertionReason(assertion),
		})
	}
	p.list.SetItems(items)
}

func (p *ProofModel) fetchProof() tea.Cmd {
	return func() tea.Msg {
		result, err := p.client.ViewEpisode(context.Background(), p.episodeID)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.ProofLoaded{
			EpisodeID:     p.episodeID,
			Proof:         proof.NewProofFromViewResult(result),
			WorkspaceDiff: result.Dashboard.Verification.WorkspaceDiff,
		}
	}
}

type assertionItem struct {
	title       string
	description string
}

func (a assertionItem) Title() string       { return a.title }
func (a assertionItem) Description() string { return a.description }
func (a assertionItem) FilterValue() string { return a.title }

func renderAssertionLine(assertion cli.VerificationAssertion) string {
	iconSet := style.Icons()
	status := style.SuccessText.Render(iconSet.Verified())
	if !assertion.Passed {
		status = style.ErrorText.Render(iconSet.Failed())
	}

	target := formatAssertionTarget(assertion.Target)
	label := assertion.Name
	if target != "" {
		label = fmt.Sprintf("%s %s", label, target)
	}
	return fmt.Sprintf("%s %s", status, label)
}

func renderAssertionReason(assertion cli.VerificationAssertion) string {
	if assertion.Passed || assertion.Reason == nil {
		return ""
	}
	return style.MutedText.Render(fmt.Sprintf("Reason: %s", *assertion.Reason))
}

func formatAssertionTarget(target interface{}) string {
	switch t := target.(type) {
	case string:
		return t
	case []string:
		return strings.Join(t, ", ")
	default:
		if target == nil {
			return ""
		}
		return fmt.Sprintf("%v", target)
	}
}

func renderPanel(title, body string, width int) string {
	heading := style.Subtitle.Render(title)
	content := lipgloss.JoinVertical(lipgloss.Left, heading, body)
	panelWidth := width - 4
	if panelWidth < 10 {
		panelWidth = width
	}
	return style.Panel.Copy().Width(panelWidth).Render(content)
}

func shortenEpisodeID(id string) string {
	if len(id) <= 12 {
		return id
	}
	return id[:8] + "…" + id[len(id)-3:]
}

func verdictTextStyle(verdict string) lipgloss.Style {
	switch verdict {
	case proof.TrustVerified:
		return style.SuccessText
	case proof.TrustFailed, proof.TrustViolated:
		return style.ErrorText
	default:
		return style.WarningText
	}
}

func verificationStyle(status string) lipgloss.Style {
	switch status {
	case proof.VerificationVerified:
		return style.SuccessText
	case proof.VerificationFailed:
		return style.ErrorText
	default:
		return style.WarningText
	}
}

func governanceStyle(status string) lipgloss.Style {
	switch status {
	case proof.GovernanceAllowed:
		return style.SuccessText
	case proof.GovernanceAudit:
		return style.WarningText
	case proof.GovernanceVetoed, proof.GovernanceViolated:
		return style.ErrorText
	default:
		return style.WarningText
	}
}

func iconForVerdict(icons style.IconSet, verdict string) string {
	switch verdict {
	case proof.TrustVerified:
		return icons.Verified()
	case proof.TrustFailed:
		return icons.Failed()
	case proof.TrustViolated:
		return icons.Violated()
	default:
		return icons.Violated()
	}
}

func iconForVerification(icons style.IconSet, status string) string {
	switch status {
	case proof.VerificationVerified:
		return icons.Verified()
	case proof.VerificationFailed:
		return icons.Failed()
	default:
		return icons.Violated()
	}
}

type proofKeyMap struct {
	Back  key.Binding
	Tabs  key.Binding
	Full  key.Binding
	Diff  key.Binding
	Audit key.Binding
	Up    key.Binding
	Down  key.Binding
}

func newProofKeyMap() proofKeyMap {
	return proofKeyMap{
		Back: key.NewBinding(
			key.WithKeys("esc"),
			key.WithHelp("esc", "back"),
		),
		Tabs: key.NewBinding(
			key.WithKeys("1", "2", "3", "tab"),
			key.WithHelp("1/2/3", "tabs"),
		),
		Full: key.NewBinding(
			key.WithKeys("p"),
			key.WithHelp("p", "full proof"),
		),
		Diff: key.NewBinding(
			key.WithKeys("d"),
			key.WithHelp("d", "diff"),
		),
		Audit: key.NewBinding(
			key.WithKeys("a"),
			key.WithHelp("a", "audit"),
		),
		Up: key.NewBinding(
			key.WithKeys("up", "k"),
			key.WithHelp("↑/k", "up"),
		),
		Down: key.NewBinding(
			key.WithKeys("down", "j"),
			key.WithHelp("↓/j", "down"),
		),
	}
}

func (k proofKeyMap) ShortHelp() []key.Binding {
	return []key.Binding{k.Back, k.Tabs, k.Full, k.Diff}
}

func (k proofKeyMap) FullHelp() [][]key.Binding {
	return [][]key.Binding{
		{k.Back, k.Tabs, k.Full, k.Diff},
		{k.Up, k.Down},
	}
}

func (p *ProofModel) reflow() {
	if p.width == 0 || p.height == 0 {
		return
	}

	p.footer = style.HelpBar.Render(p.help.View(p.keyMap))
	if p.proof == nil {
		return
	}

	contentWidth := style.DetectBreakpoint(p.width).ContentWidth(p.width)
	p.header = p.renderHeader(contentWidth)

	headerH := lipgloss.Height(p.header)
	footerH := lipgloss.Height(p.footer)
	viewportHeight := p.height - headerH - footerH
	if viewportHeight < 1 {
		viewportHeight = 1
	}

	p.viewport.Width = contentWidth
	p.viewport.Height = viewportHeight
	p.progress.Width = maxInt(20, contentWidth/3)
	p.progress.SetPercent(float64(p.trustScore()) / 100.0)
	p.viewport.SetContent(p.renderPanels(contentWidth))
}

func (p *ProofModel) verdictReason() string {
	if p.proof == nil {
		return "No proof available."
	}
	if strings.TrimSpace(p.proof.Reason) != "" {
		return p.proof.Reason
	}
	if p.proof.Governance == proof.GovernanceViolated || p.proof.Governance == proof.GovernanceVetoed {
		if p.proof.PolicyBreach != nil {
			return fmt.Sprintf("Governance breach (%s)", *p.proof.PolicyBreach)
		}
		return "Governance policy violated."
	}
	if p.proof.Verification == proof.VerificationFailed {
		if assertion := p.firstFailingAssertion(); assertion != "" {
			return assertion
		}
		return "Verification failed."
	}
	if p.proof.Verification == proof.VerificationUnverified {
		return "No verification was provided."
	}
	return "Assertions passed for this run."
}

func (p *ProofModel) firstFailingAssertion() string {
	for _, assertion := range p.proof.Assertions {
		if assertion.Passed {
			continue
		}
		target := formatAssertionTarget(assertion.Target)
		if target != "" {
			return fmt.Sprintf("%s %s", assertion.Name, target)
		}
		return assertion.Name
	}
	return ""
}

func (p *ProofModel) trustScore() int {
	if p.proof == nil {
		return 0
	}
	total := len(p.proof.Assertions)
	if total > 0 {
		passed := 0
		for _, assertion := range p.proof.Assertions {
			if assertion.Passed {
				passed++
			}
		}
		return int(float64(passed) / float64(total) * 100)
	}

	switch p.proof.TrustVerdict {
	case proof.TrustVerified:
		return 100
	case proof.TrustFailed:
		return 30
	case proof.TrustViolated:
		return 20
	default:
		return 60
	}
}

func (p *ProofModel) renderTabs() string {
	tabs := []string{
		p.tabLabel(0, "Overview"),
		p.tabLabel(1, "Tools (0)"),
		p.tabLabel(2, "Proof"),
	}
	return strings.Join(tabs, "  ")
}

func (p *ProofModel) tabLabel(index int, label string) string {
	base := fmt.Sprintf("[%d] %s", index+1, label)
	if p.tabIndex == index {
		return style.Subtitle.Render(base)
	}
	return style.MutedText.Render(base)
}

func (p *ProofModel) taskLabel() string {
	if p.proof.Task == "" {
		return "Unknown task"
	}
	return p.proof.Task
}

func (p *ProofModel) renderOverview(width int) string {
	status := verdictTextStyle(p.proof.TrustVerdict).Render("[" + p.proof.TrustVerdict + "]")
	agent := "Unknown"
	started := "Unknown"
	completed := "Unknown"
	if p.proof != nil {
		started = p.startedLabel()
		completed = p.completedLabel()
	}

	header := lipgloss.JoinVertical(lipgloss.Left,
		fmt.Sprintf("Status     %s", status),
		fmt.Sprintf("Agent      %s", agent),
		fmt.Sprintf("Started    %s", started),
		fmt.Sprintf("Completed  %s", completed),
	)

	content := []string{
		header,
		"",
		style.Subtitle.Render("Input"),
		p.taskLabel(),
		"",
		style.Subtitle.Render("Output"),
		p.outputSummary(),
		"",
		style.Subtitle.Render("Trust Status"),
		fmt.Sprintf("%s  %d%%", verdictTextStyle(p.proof.TrustVerdict).Render("["+p.proof.TrustVerdict+"]"), p.trustScore()),
		"",
		style.Subtitle.Render("Observed agents (from run events)"),
		p.renderObservedAgents(),
		"",
		style.MutedText.Render("Observed tool calls: unknown"),
	}

	return strings.Join(content, "\n")
}

func (p *ProofModel) outputSummary() string {
	if p.proof.Outcome != nil {
		if p.proof.Verification == proof.VerificationFailed || p.proof.Governance == proof.GovernanceViolated || p.proof.Governance == proof.GovernanceVetoed {
			return style.ErrorText.Render(*p.proof.Outcome)
		}
		return *p.proof.Outcome
	}
	if p.proof.Verification == proof.VerificationFailed {
		return style.ErrorText.Render("Verification failed.")
	}
	if p.proof.Verification == proof.VerificationUnverified {
		return style.MutedText.Render("No verification output recorded.")
	}
	return style.MutedText.Render("No output summary available.")
}

func (p *ProofModel) renderTools(width int) string {
	title := style.Subtitle.Render("Tool Calls")
	body := style.MutedText.Render("Observed tool calls: unknown")
	return lipgloss.JoinVertical(lipgloss.Left, title, body)
}

func (p *ProofModel) renderProofSummary(width int) string {
	scoreLine := fmt.Sprintf("%s  Trust Score  %s  %d%%",
		verdictTextStyle(p.proof.TrustVerdict).Render("["+p.proof.TrustVerdict+"]"),
		p.progress.View(),
		p.trustScore(),
	)

	verification := p.truthLine("Verification", p.proof.Verification)
	governance := p.truthLine("Governance", p.proof.Governance)
	evidence := p.truthLine("Evidence", p.proof.Evidence)
	replay := p.truthLine("Replay", p.proof.Replay)

	truths := []string{
		style.Subtitle.Render("The Four Truths"),
		"",
		verification + "    " + governance,
		evidence + "    " + replay,
		"",
		style.MutedText.Render(p.verdictReason()),
	}

	return lipgloss.JoinVertical(lipgloss.Left, scoreLine, "", strings.Join(truths, "\n"))
}

func (p *ProofModel) truthLine(label, status string) string {
	iconSet := style.Icons()
	icon := iconSet.Violated()
	render := style.WarningText.Render

	switch strings.ToUpper(status) {
	case proof.VerificationVerified, proof.GovernanceAllowed, proof.EvidenceCaptured:
		icon = iconSet.Verified()
		render = style.SuccessText.Render
	case proof.VerificationFailed, proof.GovernanceViolated, proof.GovernanceVetoed:
		icon = iconSet.Failed()
		render = style.ErrorText.Render
	default:
		icon = iconSet.Violated()
		render = style.WarningText.Render
	}

	return fmt.Sprintf("%s %s %s",
		render(icon),
		label,
		style.MutedText.Render("("+strings.ToLower(status)+")"),
	)
}

func (p *ProofModel) startedLabel() string {
	if p.proof.StartedAt != nil && strings.TrimSpace(*p.proof.StartedAt) != "" {
		return *p.proof.StartedAt
	}
	return "Unknown"
}

func (p *ProofModel) completedLabel() string {
	if p.proof.Duration != nil && *p.proof.Duration > 0 {
		return fmt.Sprintf("+%.1fs", *p.proof.Duration)
	}
	return "Unknown"
}

func (p *ProofModel) renderFullProof(width int) string {
	sections := []string{
		p.renderVerdictPanel(width),
		p.renderChangesPanel(width),
		p.renderVerificationPanel(width),
		p.renderGovernancePanel(width),
		p.renderEvidencePanel(width),
		p.renderReplayPanel(width),
	}
	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

func (p *ProofModel) renderChangesPanel(width int) string {
	body := p.renderDiffLines()
	if body == "" {
		body = style.MutedText.Render("No workspace diff captured.")
	}
	if p.isScopeBreach() {
		body = lipgloss.JoinVertical(lipgloss.Left,
			style.ErrorText.Render("OUT OF SCOPE"),
			body,
		)
	}
	return renderStatusPanel("Changes", body, width, p.proof.Governance)
}

func (p *ProofModel) renderVerdictPanel(width int) string {
	status := verdictTextStyle(p.proof.TrustVerdict).Render("[" + p.proof.TrustVerdict + "]")
	scoreLine := fmt.Sprintf("Trust Score  %s  %d%%", p.progress.View(), p.trustScore())
	reason := p.verdictReason()
	body := lipgloss.JoinVertical(lipgloss.Left,
		fmt.Sprintf("Trust Verdict  %s", status),
		scoreLine,
		style.MutedText.Render(reason),
	)
	return renderStatusPanel("Trust Verdict", body, width, p.proof.TrustVerdict)
}

func (p *ProofModel) renderVerificationPanel(width int) string {
	status := verificationStyle(p.proof.Verification).Render("[" + p.proof.Verification + "]")
	details := p.verificationDetails()
	body := lipgloss.JoinVertical(lipgloss.Left,
		fmt.Sprintf("Status       %s", status),
		style.MutedText.Render("Details      "+details),
	)
	return renderStatusPanel("Verification", body, width, p.proof.Verification)
}

func (p *ProofModel) renderEvidencePanel(width int) string {
	status := evidenceStatusLabel(p.proof.Evidence)
	scoreLine := fmt.Sprintf("Completeness  %s  %d%%", p.progress.View(), p.evidenceScore())
	artifacts := "Artifacts (0):"
	if p.diff != nil {
		artifacts = "Artifacts (1):"
	}
	body := lipgloss.JoinVertical(lipgloss.Left,
		fmt.Sprintf("%s  %s", status, scoreLine),
		style.MutedText.Render(artifacts),
	)
	return renderStatusPanel("Evidence", body, width, p.proof.Evidence)
}

func (p *ProofModel) renderReplayPanel(width int) string {
	status := "[" + strings.ToUpper(p.proof.Replay) + "]"
	body := lipgloss.JoinVertical(lipgloss.Left,
		fmt.Sprintf("Status       %s", style.MutedText.Render(status)),
		style.MutedText.Render("Replay not available yet."),
	)
	return renderStatusPanel("Replay", body, width, p.proof.Replay)
}

func (p *ProofModel) verificationDetails() string {
	switch p.proof.Verification {
	case proof.VerificationVerified:
		return "Verification passed."
	case proof.VerificationFailed:
		return "Verification failed."
	default:
		return "Verification pending."
	}
}

func (p *ProofModel) evidenceScore() int {
	if p.proof.Evidence == proof.EvidenceCaptured {
		return 100
	}
	return 0
}

func (p *ProofModel) renderObservedAgents() string {
	if p.proof == nil || len(p.proof.Agents) == 0 {
		return style.MutedText.Render("None observed.")
	}

	lines := make([]string, 0, len(p.proof.Agents))
	for _, agent := range p.proof.Agents {
		phaseSummary := formatPhaseCounts(agent.PhaseCounts)
		last := ""
		if agent.LastSummary != "" {
			last = " • last: " + truncate(agent.LastSummary, 48)
		}
		line := fmt.Sprintf("%s  %s%s", agent.Name, style.MutedText.Render(phaseSummary), style.MutedText.Render(last))
		lines = append(lines, line)
	}
	return strings.Join(lines, "\n")
}

func formatPhaseCounts(counts map[string]int) string {
	if len(counts) == 0 {
		return "no phases"
	}
	keys := make([]string, 0, len(counts))
	for key := range counts {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	parts := make([]string, 0, len(keys))
	for _, key := range keys {
		parts = append(parts, fmt.Sprintf("%s:%d", key, counts[key]))
	}
	return strings.Join(parts, " ")
}

func (p *ProofModel) governanceViolations() []string {
	var violations []string
	for _, assertion := range p.proof.Assertions {
		if assertion.Passed {
			continue
		}
		if isGovernanceAssertion(assertion.Name) {
			target := formatAssertionTarget(assertion.Target)
			if target != "" {
				violations = append(violations, fmt.Sprintf("%s %s", assertion.Name, target))
			} else {
				violations = append(violations, assertion.Name)
			}
		}
	}
	return violations
}

func isGovernanceAssertion(name string) bool {
	switch strings.ToLower(name) {
	case "only_modified",
		"within_paths",
		"no_network",
		"no_secrets",
		"no_write_outside":
		return true
	default:
		return false
	}
}

func (p *ProofModel) isScopeBreach() bool {
	return p.proof.Governance == proof.GovernanceViolated || p.proof.Governance == proof.GovernanceVetoed || len(p.governanceViolations()) > 0
}

func truncate(value string, max int) string {
	if max <= 0 || len(value) <= max {
		return value
	}
	if max < 4 {
		return value[:max]
	}
	return value[:max-3] + "..."
}

func evidenceStatusLabel(status string) string {
	switch status {
	case proof.EvidenceCaptured:
		return style.SuccessText.Render("[PRESENT]")
	default:
		return style.WarningText.Render("[MISSING]")
	}
}

func renderStatusPanel(title, body string, width int, status string) string {
	panelWidth := width - 4
	if panelWidth < 10 {
		panelWidth = width
	}
	panel := style.Panel.Copy().Width(panelWidth)
	panel = panel.BorderForeground(statusBorderColor(status))
	content := lipgloss.JoinVertical(lipgloss.Left, style.Subtitle.Render(title), body)
	return panel.Render(content)
}

func statusBorderColor(status string) lipgloss.Color {
	upper := strings.ToUpper(status)
	if upper == proof.TrustViolated || upper == proof.GovernanceViolated {
		return style.ErrorColor
	}
	switch upper {
	case proof.GovernanceVetoed, proof.VerificationFailed:
		return style.ErrorColor
	case proof.VerificationVerified, proof.GovernanceAllowed, proof.EvidenceCaptured:
		return style.SuccessColor
	default:
		return style.WarningColor
	}
}
