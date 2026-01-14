package model

import (
	"context"
	"fmt"
	"sort"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"

	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Home is the home dashboard screen model.
type Home struct {
	list     list.Model
	spinner  spinner.Model
	loading  bool
	episodes []cli.EpisodeRow
	stats    episodeStats
	agents   []msg.AgentSummary
	client   *cli.Client
	runsDir  string
	width    int
	height   int
	tabIndex int // 0 = runs, 1 = agents
}

// episodeStats holds computed statistics about episodes.
type episodeStats struct {
	Total          int
	Succeeded      int
	Unverified     int
	Failed         int
	Violated       int
	Unknown        int
	NeedsAttention int
}

// episodeItem wraps EpisodeRow for the list.Model
type episodeItem struct {
	episode cli.EpisodeRow
}

func (i episodeItem) Title() string {
	outcome := i.episode.OutcomeOrDefault()
	badge := style.GetOutcomeBadge(outcome)
	symbol := style.StatusSymbol(strings.ToUpper(badge.Style))

	var symbolStyle lipgloss.Style
	switch badge.Style {
	case "ok":
		symbolStyle = style.StatusSuccess
	case "warn":
		symbolStyle = style.StatusAudit
	case "err":
		symbolStyle = style.StatusVetoed
	default:
		symbolStyle = style.StatusPending
	}

	return fmt.Sprintf("%s %s  %s",
		symbolStyle.Render(symbol),
		style.MutedText.Render(i.episode.EpisodeShort),
		badge.Label,
	)
}

func (i episodeItem) Description() string {
	task := i.episode.Task
	if len(task) > 50 {
		task = task[:47] + "..."
	}
	return fmt.Sprintf("%s  %s  %s",
		style.DimText.Render(i.episode.Duration),
		style.DimText.Render(i.episode.StartedAt),
		task,
	)
}

func (i episodeItem) FilterValue() string {
	return i.episode.EpisodeID + " " + i.episode.Task
}

// NewHome creates a new Home model.
func NewHome(client *cli.Client) *Home {
	// Create list with custom styling
	delegate := list.NewDefaultDelegate()
	delegate.Styles.SelectedTitle = delegate.Styles.SelectedTitle.
		Foreground(style.AccentColor).
		BorderForeground(style.AccentColor)
	delegate.Styles.SelectedDesc = delegate.Styles.SelectedDesc.
		Foreground(style.MutedColor)
	delegate.SetSpacing(0)

	l := list.New([]list.Item{}, delegate, 0, 0)
	l.Title = ""
	l.SetShowTitle(false)
	l.SetShowStatusBar(false)
	l.SetFilteringEnabled(true)
	l.SetShowFilter(false)
	l.SetShowHelp(false)
	l.KeyMap.Quit.Unbind()

	// Create spinner
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	return &Home{
		list:     l,
		spinner:  s,
		loading:  true,
		client:   client,
		runsDir:  client.RunsDir,
		tabIndex: 0,
	}
}

// Init implements tea.Model.
func (h *Home) Init() tea.Cmd {
	return tea.Batch(
		h.spinner.Tick,
		h.fetchEpisodes(),
	)
}

// Update implements tea.Model.
func (h *Home) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case tea.WindowSizeMsg:
		h.width = m.Width
		h.height = m.Height
		return h, nil

	case msg.EpisodesLoaded:
		h.loading = false
		h.episodes = m.Episodes
		h.stats = computeStats(m.Episodes)
		items := make([]list.Item, len(m.Episodes))
		for i, ep := range m.Episodes {
			items[i] = episodeItem{episode: ep}
		}
		h.list.SetItems(items)
		if len(m.Episodes) > 0 {
			return h, h.fetchAgentSummary(m.Episodes[0].EpisodeID)
		}
		return h, nil

	case msg.AgentSummaryLoaded:
		h.agents = m.Agents
		return h, nil

	case msg.Error:
		h.loading = false
		return h, nil

	case tea.KeyMsg:
		if h.loading {
			return h, nil
		}
		switch m.String() {
		case "1":
			h.tabIndex = 0
			return h, nil
		case "2":
			h.tabIndex = 1
			return h, nil
		case "tab":
			h.tabIndex = (h.tabIndex + 1) % 2
			return h, nil
		case "enter":
			selected := h.list.SelectedItem()
			if selected != nil {
				ep := selected.(episodeItem).episode
				return h, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenDetail, Payload: ep.EpisodeID}
				}
			}
		case "e":
			selected := h.list.SelectedItem()
			if selected != nil {
				ep := selected.(episodeItem).episode
				return h, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenEvents, Payload: ep.EpisodeID}
				}
			}
		case "b":
			return h, func() tea.Msg {
				return msg.NavigateTo{Screen: msg.ScreenBrowse, Payload: nil}
			}
		case "p":
			selected := h.list.SelectedItem()
			if selected != nil {
				ep := selected.(episodeItem).episode
				return h, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenProof, Payload: ep.EpisodeID}
				}
			}
		case "n":
			return h, func() tea.Msg {
				return msg.NavigateTo{Screen: msg.ScreenRun, Payload: nil}
			}
		case "r":
			h.loading = true
			return h, tea.Batch(h.spinner.Tick, h.fetchEpisodes())
		case "/":
			h.list.SetShowFilter(true)
			var cmd tea.Cmd
			h.list, cmd = h.list.Update(m)
			return h, cmd
		}
	}

	var cmd tea.Cmd
	if h.loading {
		h.spinner, cmd = h.spinner.Update(m)
		return h, cmd
	}

	h.list, cmd = h.list.Update(m)
	return h, cmd
}

// View implements tea.Model.
func (h *Home) View() string {
	if h.loading {
		return h.viewLoading()
	}
	return h.viewDashboard()
}

func (h *Home) viewLoading() string {
	content := lipgloss.JoinVertical(lipgloss.Center,
		"",
		h.spinner.View(),
		"",
		style.MutedText.Render("Loading episodes..."),
	)
	return lipgloss.Place(h.width, h.height, lipgloss.Center, lipgloss.Center, content)
}

func (h *Home) viewDashboard() string {
	contentWidth := style.DetectBreakpoint(h.width).ContentWidth(h.width)
	header := h.renderHeader()
	hero := h.renderHero(contentWidth)
	tabs := h.renderTabs()
	help := style.HelpBar.Render("1/2: tabs  enter: view  b: browse  p: proof  e: events  n: run  r: refresh  /: filter  q: quit")

	headerH := lipgloss.Height(header)
	heroH := lipgloss.Height(hero)
	tabsH := lipgloss.Height(tabs)
	helpH := lipgloss.Height(help)
	bodyH := h.height - headerH - heroH - tabsH - helpH - 2
	if bodyH < 6 {
		bodyH = 6
	}

	body := h.renderBody(contentWidth, bodyH)

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		hero,
		tabs,
		body,
		help,
	)
}

func (h *Home) renderHeader() string {
	logo := style.BrandStyle.Bold(true).Render("noesis")
	title := lipgloss.JoinHorizontal(lipgloss.Bottom, logo, style.MutedText.Render(" > Home"))
	welcome := style.DimText.Render("Agentic AI terminal experience")
	divider := style.DimText.Render(strings.Repeat("─", maxInt(10, h.width/3)))

	return lipgloss.JoinVertical(lipgloss.Left, title, welcome, divider)
}

func (h *Home) renderHero(width int) string {
	title := style.BrandStyle.Render("noesis")
	logo := strings.Join([]string{
		" _   _  ____  _____  ____ ___ ___ ",
		"| \\ | |/ __ \\| ____|/ ___|_ _/ _ \\",
		"|  \\| | |  | |  _|  \\___ \\| | | | |",
		"| |\\  | |__| | |___  ___) | | |_| |",
		"|_| \\_|\\____/|_____| |____/___\\___/",
	}, "\n")
	logo = style.InfoText.Render(logo)
	tagline := style.MutedText.Render("Understanding, made observable.")
	version := style.DimText.Render("v0.1.0")
	subtitle := style.MutedText.Render("Agentic AI Framework")

	content := lipgloss.JoinVertical(lipgloss.Center,
		logo,
		tagline,
		version,
		subtitle,
	)

	panel := style.Panel.Copy().Width(width)
	panel = panel.BorderForeground(style.AccentColor)
	return panel.Render(lipgloss.JoinVertical(lipgloss.Left, title, "", content))
}

func (h *Home) renderTabs() string {
	runs := h.tabLabel(0, "Runs")
	agents := h.tabLabel(1, "Agents")
	return strings.Join([]string{runs, agents}, "  ")
}

func (h *Home) tabLabel(index int, label string) string {
	base := fmt.Sprintf("[%d] %s", index+1, label)
	if h.tabIndex == index {
		return style.Subtitle.Render(base)
	}
	return style.MutedText.Render(base)
}

func (h *Home) renderBody(width, height int) string {
	if h.tabIndex == 0 {
		return h.renderRunsPanel(width, height)
	}
	return h.renderAgentsPanel(width, height)
}

func (h *Home) renderRunsPanel(width, height int) string {
	sectionTitle := style.Subtitle.Render("Recent Episodes")

	if len(h.episodes) == 0 {
		empty := style.MutedText.Render("No episodes yet. Press 'n' to start a new run.")
		return lipgloss.JoinVertical(lipgloss.Left, sectionTitle, "", empty)
	}

	listHeight := height - 2
	if listHeight < 4 {
		listHeight = 4
	}
	h.list.SetSize(width-4, listHeight)
	return lipgloss.JoinVertical(lipgloss.Left, sectionTitle, "", h.list.View())
}

func (h *Home) renderAgentsPanel(width, height int) string {
	left := h.renderAgentList(width/2 - 2)
	right := h.renderAgentSummaryBox(width/2 - 2)

	if style.DetectBreakpoint(width) == style.Compact {
		return lipgloss.JoinVertical(lipgloss.Left, left, "", right)
	}
	return lipgloss.JoinHorizontal(lipgloss.Top, left, "  ", right)
}

func (h *Home) renderAgentList(width int) string {
	title := style.Subtitle.Render("Observed agents (from run events)")
	if len(h.agents) == 0 {
		return lipgloss.JoinVertical(lipgloss.Left, title, style.MutedText.Render("No observed agents."))
	}

	lines := make([]string, 0, len(h.agents))
	for _, agent := range h.agents {
		phaseSummary := formatPhaseCounts(agent.PhaseCounts)
		line := fmt.Sprintf("• %s  %s", agent.Name, style.MutedText.Render(phaseSummary))
		lines = append(lines, line)
	}
	return lipgloss.JoinVertical(lipgloss.Left, title, strings.Join(lines, "\n"))
}

func (h *Home) renderAgentSummaryBox(width int) string {
	panel := style.Panel.Copy().Width(width)
	panel = panel.BorderForeground(style.MutedColor)

	total := len(h.agents)
	body := lipgloss.JoinVertical(lipgloss.Left,
		style.Subtitle.Render("Observed Agents"),
		style.MutedText.Render(fmt.Sprintf("%d agents observed", total)),
	)
	return panel.Render(body)
}

// SetSize updates the dimensions.
func (h *Home) SetSize(width, height int) {
	h.width = width
	h.height = height
	h.list.SetSize(width-4, height-20)
}

func (h *Home) fetchEpisodes() tea.Cmd {
	return func() tea.Msg {
		result, err := h.client.ListEpisodes(context.Background(), 50)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.EpisodesLoaded{
			Episodes:   result.Episodes,
			TotalCount: result.TotalCount,
		}
	}
}

func (h *Home) fetchAgentSummary(episodeID string) tea.Cmd {
	return func() tea.Msg {
		result, err := h.client.ViewEpisode(context.Background(), episodeID)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.AgentSummaryLoaded{
			EpisodeID: episodeID,
			Agents:    summarizeAgents(result.Dashboard.TimelineRows),
		}
	}
}

func summarizeAgents(rows []cli.TimelineRow) []msg.AgentSummary {
	agents := map[string]*msg.AgentSummary{}
	for _, row := range rows {
		name := strings.TrimSpace(row.Agent)
		if name == "" {
			name = "unknown"
		}
		agent := agents[name]
		if agent == nil {
			agent = &msg.AgentSummary{
				Name:        name,
				PhaseCounts: map[string]int{},
			}
			agents[name] = agent
		}
		agent.EventCount++
		phase := strings.ToLower(strings.TrimSpace(row.Phase))
		if phase != "" {
			agent.PhaseCounts[phase]++
		}
	}
	out := make([]msg.AgentSummary, 0, len(agents))
	for _, agent := range agents {
		out = append(out, *agent)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].Name < out[j].Name
	})
	return out
}

func computeStats(episodes []cli.EpisodeRow) episodeStats {
	stats := episodeStats{
		Total: len(episodes),
	}

	for _, ep := range episodes {
		outcome := strings.ToLower(ep.OutcomeOrDefault())
		switch outcome {
		case "success":
			stats.Succeeded++
		case "success_unverified":
			stats.Unverified++
		case "goal_not_achieved", "error":
			stats.Failed++
		case "violated":
			stats.Violated++
		default:
			if ep.IsSuccess() {
				stats.Succeeded++
			} else {
				stats.Unknown++
			}
		}
	}
	stats.NeedsAttention = stats.Failed + stats.Violated + stats.Unknown

	return stats
}
