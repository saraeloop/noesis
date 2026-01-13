package model

import (
	"context"
	"fmt"
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
	list       list.Model
	spinner    spinner.Model
	loading    bool
	episodes   []cli.EpisodeRow
	stats      episodeStats
	client     *cli.Client
	runsDir    string
	width      int
	height     int
	focusIndex int // 0 = actions, 1 = episodes list
}

// episodeStats holds computed statistics about episodes.
type episodeStats struct {
	Total       int
	Succeeded   int
	Failed      int
	SuccessRate float64
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
		list:       l,
		spinner:    s,
		loading:    true,
		client:     client,
		runsDir:    client.RunsDir,
		focusIndex: 1, // Start with episodes focused
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
		return h, nil

	case msg.Error:
		h.loading = false
		return h, nil

	case tea.KeyMsg:
		if h.loading {
			return h, nil
		}
		switch m.String() {
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
	// Header with brand
	header := h.renderHeader()

	// Stats cards
	stats := h.renderStats()

	// Quick actions
	actions := h.renderActions()

	// Episodes section
	episodes := h.renderEpisodes()

	// Help bar
	help := style.HelpBar.Render("enter: view  e: events  n: new run  r: refresh  /: filter  q: quit")

	// Calculate available height
	headerH := lipgloss.Height(header)
	statsH := lipgloss.Height(stats)
	actionsH := lipgloss.Height(actions)
	helpH := lipgloss.Height(help)
	episodesH := h.height - headerH - statsH - actionsH - helpH - 4

	if episodesH < 5 {
		episodesH = 5
	}
	h.list.SetSize(h.width-4, episodesH-3)

	// Re-render episodes with correct size
	episodes = h.renderEpisodes()

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		"",
		stats,
		"",
		actions,
		"",
		episodes,
		"",
		help,
	)
}

func (h *Home) renderHeader() string {
	// Logo/Brand
	logo := style.BrandStyle.Bold(true).Render("Noesis")
	tagline := style.MutedText.Render(" Cognitive Framework")

	title := lipgloss.JoinHorizontal(lipgloss.Bottom, logo, tagline)

	// Welcome message
	welcome := style.DimText.Render("Observable reasoning for autonomous agents")

	// Runs directory indicator
	runsInfo := ""
	if h.runsDir != "" {
		runsInfo = style.DimText.Render("runs: " + h.runsDir)
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		"",
		"  "+title,
		"  "+welcome,
		"  "+runsInfo,
	)
}

func (h *Home) renderStats() string {
	// Create stat cards
	totalCard := h.statCard("Episodes", fmt.Sprintf("%d", h.stats.Total), style.InfoColor)
	successCard := h.statCard("Succeeded", fmt.Sprintf("%d", h.stats.Succeeded), style.SuccessColor)
	failedCard := h.statCard("Failed", fmt.Sprintf("%d", h.stats.Failed), style.ErrorColor)

	rateStr := "--"
	if h.stats.Total > 0 {
		rateStr = fmt.Sprintf("%.0f%%", h.stats.SuccessRate*100)
	}
	rateCard := h.statCard("Success Rate", rateStr, style.AccentColor)

	// Arrange cards horizontally
	cards := lipgloss.JoinHorizontal(lipgloss.Top,
		totalCard, "  ",
		successCard, "  ",
		failedCard, "  ",
		rateCard,
	)

	return "  " + cards
}

func (h *Home) statCard(label, value string, color lipgloss.Color) string {
	valueStyle := lipgloss.NewStyle().
		Bold(true).
		Foreground(color)

	labelStyle := style.DimText

	cardStyle := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("#3F3F46")).
		Padding(0, 2).
		Width(16)

	content := lipgloss.JoinVertical(lipgloss.Center,
		valueStyle.Render(value),
		labelStyle.Render(label),
	)

	return cardStyle.Render(content)
}

func (h *Home) renderActions() string {
	actionStyle := lipgloss.NewStyle().
		Foreground(style.AccentColor)

	keyStyle := lipgloss.NewStyle().
		Bold(true).
		Foreground(style.BrandColor)

	actions := lipgloss.JoinHorizontal(lipgloss.Center,
		keyStyle.Render("n"), actionStyle.Render(" New Run"), "    ",
		keyStyle.Render("r"), actionStyle.Render(" Refresh"), "    ",
		keyStyle.Render("/"), actionStyle.Render(" Search"),
	)

	return "  " + actions
}

func (h *Home) renderEpisodes() string {
	sectionTitle := style.Subtitle.Render("Recent Episodes")

	if len(h.episodes) == 0 {
		empty := style.MutedText.Render("No episodes yet. Press 'n' to start a new run.")
		return lipgloss.JoinVertical(lipgloss.Left,
			"  "+sectionTitle,
			"",
			"  "+empty,
		)
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		"  "+sectionTitle,
		"",
		"  "+h.list.View(),
	)
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

func computeStats(episodes []cli.EpisodeRow) episodeStats {
	stats := episodeStats{
		Total: len(episodes),
	}

	for _, ep := range episodes {
		if ep.IsSuccess() {
			stats.Succeeded++
		} else {
			stats.Failed++
		}
	}

	if stats.Total > 0 {
		stats.SuccessRate = float64(stats.Succeeded) / float64(stats.Total)
	}

	return stats
}
