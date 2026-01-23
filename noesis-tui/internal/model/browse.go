package model

import (
	"context"
	"fmt"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"
	"noesis.dev/tui/internal/ui/dashboard"

	"github.com/charmbracelet/bubbles/help"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/list"
	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Browse presents episodes list with a detail pane.
type Browse struct {
	list      list.Model
	viewport  viewport.Model
	spinner   spinner.Model
	help      help.Model
	keyMap    browseKeyMap
	client    *cli.Client
	episodes  []cli.EpisodeRow
	dashboard *cli.Dashboard
	loading   bool
	width     int
	height    int
	header    string
	footer    string
	bodyH     int
}

// NewBrowse creates a new Browse model.
func NewBrowse(client *cli.Client) *Browse {
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

	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	h := help.New()
	h.ShowAll = false

	return &Browse{
		list:    l,
		spinner: s,
		loading: true,
		client:  client,
		help:    h,
		keyMap:  newBrowseKeyMap(),
	}
}

// Init implements tea.Model.
func (b *Browse) Init() tea.Cmd {
	return tea.Batch(
		b.spinner.Tick,
		b.fetchEpisodes(),
	)
}

// Update implements tea.Model.
func (b *Browse) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case tea.WindowSizeMsg:
		b.width = m.Width
		b.height = m.Height
		b.reflow()
		return b, nil

	case msg.EpisodesLoaded:
		b.loading = false
		b.episodes = m.Episodes
		items := make([]list.Item, len(m.Episodes))
		for i, ep := range m.Episodes {
			items[i] = episodeBrowseItem{episode: ep}
		}
		b.list.SetItems(items)
		b.reflow()
		if len(m.Episodes) > 0 {
			return b, b.fetchDashboard(m.Episodes[0].EpisodeID)
		}
		return b, nil

	case msg.DashboardLoaded:
		b.dashboard = &m.Dashboard
		b.reflow()
		return b, nil

	case msg.Error:
		b.loading = false
		return b, nil

	case tea.KeyMsg:
		switch m.String() {
		case "d":
			if b.list.SelectedItem() != nil {
				ep := b.list.SelectedItem().(episodeBrowseItem).episode
				return b, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenChanges, Payload: ep.EpisodeID}
				}
			}
		case "p":
			if b.list.SelectedItem() != nil {
				ep := b.list.SelectedItem().(episodeBrowseItem).episode
				return b, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenProof, Payload: ep.EpisodeID}
				}
			}
		case "e":
			if b.list.SelectedItem() != nil {
				ep := b.list.SelectedItem().(episodeBrowseItem).episode
				return b, func() tea.Msg {
					return msg.NavigateTo{Screen: msg.ScreenEvents, Payload: ep.EpisodeID}
				}
			}
		case "/":
			b.list.SetShowFilter(true)
		}
	}

	var cmd tea.Cmd
	if b.loading {
		b.spinner, cmd = b.spinner.Update(m)
		return b, cmd
	}

	var listCmd tea.Cmd
	b.list, listCmd = b.list.Update(m)

	if b.list.SelectedItem() != nil {
		selected := b.list.SelectedItem().(episodeBrowseItem).episode
		if b.dashboard == nil || selected.EpisodeID != b.dashboard.Header.EpisodeID {
			return b, tea.Batch(listCmd, b.fetchDashboard(selected.EpisodeID))
		}
	}

	b.viewport, cmd = b.viewport.Update(m)
	return b, tea.Batch(listCmd, cmd)
}

// View implements tea.Model.
func (b *Browse) View() string {
	if b.loading {
		return b.viewLoading()
	}

	content := lipgloss.JoinVertical(lipgloss.Left,
		b.header,
		b.renderBody(),
		b.footer,
	)
	return lipgloss.Place(b.width, b.height, lipgloss.Left, lipgloss.Top, content)
}

// SetSize updates dimensions.
func (b *Browse) SetSize(width, height int) {
	b.width = width
	b.height = height
	b.reflow()
}

func (b *Browse) viewLoading() string {
	content := lipgloss.JoinVertical(lipgloss.Center,
		b.spinner.View(),
		style.MutedText.Render("Loading episodes..."),
	)
	return lipgloss.Place(b.width, b.height, lipgloss.Center, lipgloss.Center, content)
}

func (b *Browse) renderBody() string {
	if b.width == 0 || b.height == 0 {
		return ""
	}

	if style.DetectBreakpoint(b.width) == style.Compact {
		listH := maxInt(8, b.bodyH/3)
		detailH := b.bodyH - listH - 1
		if detailH < 6 {
			detailH = 6
		}
		return lipgloss.JoinVertical(lipgloss.Left,
			b.renderListPane(b.width, listH),
			b.renderDetailPane(b.width, detailH),
		)
	}

	leftWidth, rightWidth := b.splitWidths()
	left := b.renderListPane(leftWidth, b.bodyH)
	right := b.renderDetailPane(rightWidth, b.bodyH)
	return lipgloss.JoinHorizontal(lipgloss.Top, left, right)
}

func (b *Browse) renderListPane(width, height int) string {
	title := style.Subtitle.Render("Episodes")
	listWidth := width - 2
	if listWidth < 20 {
		listWidth = width
	}
	listHeight := height - 6
	if listHeight < 4 {
		listHeight = 4
	}
	b.list.SetSize(listWidth, listHeight)

	content := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		b.list.View(),
	)

	return style.Panel.Copy().Width(width).Render(content)
}

func (b *Browse) renderDetailPane(width, height int) string {
	title := style.Subtitle.Render("Details")
	body := style.MutedText.Render("Select an episode to inspect.")
	if b.dashboard != nil {
		body = dashboard.RenderDashboard(b.dashboard)
	}

	b.viewport.Width = width - 2
	if height > 0 {
		b.viewport.Height = height - 6
		if b.viewport.Height < 3 {
			b.viewport.Height = 3
		}
	}
	b.viewport.SetContent(body)

	content := lipgloss.JoinVertical(lipgloss.Left, title, "", b.viewport.View())
	return style.Panel.Copy().Width(width).Render(content)
}

func (b *Browse) splitWidths() (int, int) {
	contentWidth := style.DetectBreakpoint(b.width).ContentWidth(b.width)
	leftWidth := max(30, contentWidth/3)
	rightWidth := contentWidth - leftWidth - 2
	if rightWidth < 30 {
		rightWidth = 30
		leftWidth = contentWidth - rightWidth - 2
	}
	return leftWidth, rightWidth
}

func (b *Browse) reflow() {
	if b.width == 0 || b.height == 0 {
		return
	}
	b.header = b.renderHeader()
	b.footer = style.HelpBar.Render(b.help.View(b.keyMap))

	headerH := lipgloss.Height(b.header)
	footerH := lipgloss.Height(b.footer)
	b.bodyH = b.height - headerH - footerH - 2
	if b.bodyH < 6 {
		b.bodyH = 6
	}
}

func (b *Browse) renderHeader() string {
	title := style.Title.Render("BROWSE")
	sub := style.MutedText.Render("Episodes • live evidence • verification")
	return lipgloss.JoinVertical(lipgloss.Left, title, sub)
}

func (b *Browse) fetchEpisodes() tea.Cmd {
	return func() tea.Msg {
		result, err := b.client.ListEpisodes(context.Background(), 200)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.EpisodesLoaded{
			Episodes:   result.Episodes,
			TotalCount: result.TotalCount,
		}
	}
}

func (b *Browse) fetchDashboard(episodeID string) tea.Cmd {
	return func() tea.Msg {
		result, err := b.client.ViewEpisode(context.Background(), episodeID)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.DashboardLoaded{
			EpisodeID: episodeID,
			Dashboard: result.Dashboard,
			Artifacts: result.Artifacts,
		}
	}
}

type episodeBrowseItem struct {
	episode cli.EpisodeRow
}

func (i episodeBrowseItem) Title() string {
	status := classifyEpisode(i.episode)
	symbol := symbolForSeverity(status.Severity)

	var symbolStyle lipgloss.Style
	switch status.Severity {
	case "ok":
		symbolStyle = style.StatusSuccess
	case "warn":
		symbolStyle = style.StatusAudit
	case "err":
		symbolStyle = style.StatusError
	default:
		symbolStyle = style.StatusPending
	}

	return fmt.Sprintf("%s %s  %s",
		symbolStyle.Render(symbol),
		style.MutedText.Render(shortEpisodeID(i.episode)),
		status.Label,
	)
}

func (i episodeBrowseItem) Description() string {
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

func (i episodeBrowseItem) FilterValue() string {
	return i.episode.EpisodeID + " " + i.episode.Task
}

type browseKeyMap struct {
	Back   key.Binding
	Filter key.Binding
	Proof  key.Binding
	Events key.Binding
	Diff   key.Binding
}

func newBrowseKeyMap() browseKeyMap {
	return browseKeyMap{
		Back: key.NewBinding(
			key.WithKeys("esc"),
			key.WithHelp("esc", "back"),
		),
		Filter: key.NewBinding(
			key.WithKeys("/"),
			key.WithHelp("/", "filter"),
		),
		Proof: key.NewBinding(
			key.WithKeys("p"),
			key.WithHelp("p", "proof"),
		),
		Events: key.NewBinding(
			key.WithKeys("e"),
			key.WithHelp("e", "events"),
		),
		Diff: key.NewBinding(
			key.WithKeys("d"),
			key.WithHelp("d", "diff"),
		),
	}
}

func (k browseKeyMap) ShortHelp() []key.Binding {
	return []key.Binding{k.Back, k.Filter, k.Proof, k.Diff}
}

func (k browseKeyMap) FullHelp() [][]key.Binding {
	return [][]key.Binding{
		{k.Back, k.Filter},
		{k.Proof, k.Diff},
	}
}
