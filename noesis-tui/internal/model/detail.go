package model

import (
	"context"
	"fmt"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"
	"noesis.dev/tui/internal/ui/dashboard"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Detail is the episode detail/dashboard screen model.
type Detail struct {
	episodeID string
	dashboard *cli.Dashboard
	artifacts map[string]string
	loading   bool

	viewport viewport.Model
	spinner  spinner.Model
	client   *cli.Client
	width    int
	height   int
}

// NewDetail creates a new Detail model.
func NewDetail(client *cli.Client, episodeID string) *Detail {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	return &Detail{
		episodeID: episodeID,
		loading:   true,
		spinner:   s,
		client:    client,
	}
}

// Init implements tea.Model.
func (d *Detail) Init() tea.Cmd {
	return tea.Batch(
		d.spinner.Tick,
		d.fetchDashboard(),
	)
}

// Update implements tea.Model.
func (d *Detail) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case msg.DashboardLoaded:
		d.loading = false
		d.dashboard = &m.Dashboard
		d.artifacts = m.Artifacts
		d.viewport.SetContent(d.renderDashboard())
		return d, nil

	case msg.Error:
		d.loading = false
		return d, nil

	case tea.KeyMsg:
		switch m.String() {
		case "e":
			return d, func() tea.Msg {
				return msg.NavigateTo{Screen: msg.ScreenEvents, Payload: d.episodeID}
			}
		case "p":
			return d, func() tea.Msg {
				return msg.NavigateTo{Screen: msg.ScreenProof, Payload: d.episodeID}
			}
		}
	}

	var cmd tea.Cmd
	if d.loading {
		d.spinner, cmd = d.spinner.Update(m)
		return d, cmd
	}

	d.viewport, cmd = d.viewport.Update(m)
	return d, cmd
}

// View implements tea.Model.
func (d *Detail) View() string {
	if d.loading {
		return d.viewLoading()
	}
	return d.viewDashboard()
}

func (d *Detail) viewLoading() string {
	content := lipgloss.JoinVertical(lipgloss.Center,
		d.spinner.View(),
		style.MutedText.Render("Loading episode..."),
	)
	return lipgloss.Place(d.width, d.height, lipgloss.Center, lipgloss.Center, content)
}

func (d *Detail) viewDashboard() string {
	if d.dashboard == nil {
		return style.ErrorText.Render("No dashboard data")
	}

	header := d.renderHeader()
	help := style.HelpBar.Render("p: proof • e: events • ↑/↓: scroll • esc: back • q: quit")

	headerHeight := lipgloss.Height(header)
	helpHeight := lipgloss.Height(help)
	viewportHeight := d.height - headerHeight - helpHeight - 2

	d.viewport.Width = d.width
	d.viewport.Height = viewportHeight

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		d.viewport.View(),
		help,
	)
}

func (d *Detail) renderHeader() string {
	if d.dashboard == nil {
		return ""
	}

	h := d.dashboard.Header
	outcome := d.dashboard.Verification.Outcome
	outcomeStr := "unknown"
	if outcome.Status != nil {
		outcomeStr = *outcome.Status
	}

	badge := style.GetOutcomeBadge(outcomeStr)
	var badgeStyle lipgloss.Style
	switch badge.Style {
	case "ok":
		badgeStyle = style.BadgeSuccess
	case "warn":
		badgeStyle = style.BadgeWarning
	case "err":
		badgeStyle = style.BadgeError
	default:
		badgeStyle = style.BadgeMuted
	}

	title := fmt.Sprintf(" Episode: %s ", h.EpisodeID)
	status := badgeStyle.Render(badge.Label)

	return lipgloss.JoinHorizontal(lipgloss.Top,
		style.Header.Render(title),
		" ",
		status,
	)
}

func (d *Detail) renderDashboard() string {
	if d.dashboard == nil {
		return ""
	}
	return dashboard.RenderDashboard(d.dashboard)
}

func (d *Detail) renderExecutionMap() string {
	if d.dashboard == nil {
		return ""
	}

	em := d.dashboard.ExecutionMap
	phases := []cli.ExecutionPhase{em.Observe, em.Act, em.Verify, em.Outcome}

	var parts []string
	for i, phase := range phases {
		symbol := style.StatusSymbol(phase.Status)
		var symbolStyle lipgloss.Style
		switch phase.Status {
		case "OK", "PASSED":
			symbolStyle = style.StatusSuccess
		case "ERROR", "FAILED", "VETOED":
			symbolStyle = style.StatusVetoed
		case "SKIPPED":
			symbolStyle = style.StatusSkipped
		default:
			symbolStyle = style.StatusPending
		}

		part := lipgloss.JoinVertical(lipgloss.Center,
			style.Subtitle.Render(phase.Phase),
			symbolStyle.Render(symbol),
			style.DimText.Render(phase.Status),
		)
		parts = append(parts, part)

		if i < len(phases)-1 {
			arrow := style.MutedText.Render(" → ")
			parts = append(parts, arrow)
		}
	}

	title := style.Title.Render("Execution Map")
	map_ := lipgloss.JoinHorizontal(lipgloss.Center, parts...)

	return lipgloss.JoinVertical(lipgloss.Left, title, "", map_)
}

func (d *Detail) renderVerification() string {
	if d.dashboard == nil {
		return ""
	}

	v := d.dashboard.Verification
	title := style.Title.Render("Verification")

	var lines []string

	// Adapter result
	if v.AdapterResult != nil {
		lines = append(lines, fmt.Sprintf("  Adapter: %s", *v.AdapterResult))
	}

	// Outcome
	if v.Outcome.Status != nil {
		lines = append(lines, fmt.Sprintf("  Outcome: %s", *v.Outcome.Status))
	}
	if v.Outcome.Summary != nil {
		lines = append(lines, fmt.Sprintf("  Summary: %s", *v.Outcome.Summary))
	}

	// Provided/Passed
	if v.Provided != nil {
		lines = append(lines, fmt.Sprintf("  Provided: %v", *v.Provided))
	}
	if v.Passed != nil {
		symbol := style.Check
		st := style.SuccessText
		if !*v.Passed {
			symbol = style.Cross
			st = style.ErrorText
		}
		lines = append(lines, fmt.Sprintf("  Passed: %s %v", st.Render(symbol), *v.Passed))
	}

	// Error
	if v.Error != nil {
		lines = append(lines, style.ErrorText.Render(fmt.Sprintf("  Error: %s", *v.Error)))
	}

	// Assertions
	if len(v.Assertions) > 0 {
		lines = append(lines, "  Assertions:")
		for _, a := range v.Assertions {
			symbol := style.Check
			st := style.SuccessText
			if !a.Passed {
				symbol = style.Cross
				st = style.ErrorText
			}
			lines = append(lines, fmt.Sprintf("    %s %s", st.Render(symbol), a.Name))
		}
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func (d *Detail) renderKPIs() string {
	if d.dashboard == nil {
		return ""
	}

	k := d.dashboard.KPIs
	title := style.Title.Render("KPIs")

	var lines []string
	if k.SuccessPct != nil {
		lines = append(lines, fmt.Sprintf("  Success: %.0f%%", *k.SuccessPct))
	}
	if k.PlanAdherence != nil {
		lines = append(lines, fmt.Sprintf("  Plan Adherence: %.0f%%", *k.PlanAdherence*100))
	}
	if k.VetoCount != nil {
		lines = append(lines, fmt.Sprintf("  Veto Count: %d", *k.VetoCount))
	}
	if k.ToolCoverage != nil {
		lines = append(lines, fmt.Sprintf("  Tool Coverage: %.0f%%", *k.ToolCoverage*100))
	}
	if k.FirstAction != nil {
		lines = append(lines, fmt.Sprintf("  First Action: %s", *k.FirstAction))
	}

	if len(lines) == 0 {
		lines = append(lines, style.DimText.Render("  No KPI data"))
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func (d *Detail) renderPhaseBreakdown() string {
	if d.dashboard == nil || len(d.dashboard.PhaseBreakdown) == 0 {
		return ""
	}

	title := style.Title.Render("Phase Timing")

	var lines []string
	for _, p := range d.dashboard.PhaseBreakdown {
		lines = append(lines, fmt.Sprintf("  %s: %dms", p.Phase, p.Ms))
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

func (d *Detail) renderTimeline() string {
	if d.dashboard == nil || len(d.dashboard.TimelineRows) == 0 {
		return ""
	}

	title := style.Title.Render("Timeline")

	var lines []string
	for _, row := range d.dashboard.TimelineRows {
		symbol := style.PhaseSymbol(row.Phase)
		phaseStyle := style.PhaseStyle(row.Phase)

		line := fmt.Sprintf("  %s %s %s %s",
			style.DimText.Render(row.DtStr),
			phaseStyle.Render(symbol+" "+row.Phase),
			style.MutedText.Render(row.Agent),
			row.Summary,
		)
		lines = append(lines, line)
	}

	content := strings.Join(lines, "\n")
	return lipgloss.JoinVertical(lipgloss.Left, title, content)
}

// SetSize updates the dimensions.
func (d *Detail) SetSize(width, height int) {
	d.width = width
	d.height = height
	d.viewport = viewport.New(width, height-6)
	d.viewport.SetContent(d.renderDashboard())
}

func (d *Detail) fetchDashboard() tea.Cmd {
	return func() tea.Msg {
		result, err := d.client.ViewEpisode(context.Background(), d.episodeID)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.DashboardLoaded{
			EpisodeID: d.episodeID,
			Dashboard: result.Dashboard,
			Artifacts: result.Artifacts,
		}
	}
}
