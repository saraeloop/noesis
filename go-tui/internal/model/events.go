package model

import (
	"context"
	"fmt"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Available phase filters
var phaseFilters = []string{
	"all", "start", "observe", "interpret", "plan",
	"governance", "act", "reflect", "learn", "terminate", "error",
}

// Events is the events viewer screen model.
type Events struct {
	episodeID   string
	events      []cli.Event
	filtered    []cli.Event
	loading     bool
	activePhase int

	viewport viewport.Model
	spinner  spinner.Model
	client   *cli.Client
	width    int
	height   int
}

// NewEvents creates a new Events model.
func NewEvents(client *cli.Client, episodeID string) *Events {
	s := spinner.New()
	s.Spinner = spinner.Dot
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	return &Events{
		episodeID:   episodeID,
		loading:     true,
		activePhase: 0, // "all"
		spinner:     s,
		client:      client,
	}
}

// Init implements tea.Model.
func (e *Events) Init() tea.Cmd {
	return tea.Batch(
		e.spinner.Tick,
		e.fetchEvents(),
	)
}

// Update implements tea.Model.
func (e *Events) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case msg.EventsLoaded:
		e.loading = false
		e.events = m.Events
		e.applyFilter()
		e.viewport.SetContent(e.renderEvents())
		return e, nil

	case msg.Error:
		e.loading = false
		return e, nil

	case tea.KeyMsg:
		if e.loading {
			return e, nil
		}
		switch m.String() {
		case "left", "h":
			if e.activePhase > 0 {
				e.activePhase--
				e.applyFilter()
				e.viewport.SetContent(e.renderEvents())
			}
			return e, nil
		case "right", "l":
			if e.activePhase < len(phaseFilters)-1 {
				e.activePhase++
				e.applyFilter()
				e.viewport.SetContent(e.renderEvents())
			}
			return e, nil
		case "tab":
			e.activePhase = (e.activePhase + 1) % len(phaseFilters)
			e.applyFilter()
			e.viewport.SetContent(e.renderEvents())
			return e, nil
		}
	}

	var cmd tea.Cmd
	if e.loading {
		e.spinner, cmd = e.spinner.Update(m)
		return e, cmd
	}

	e.viewport, cmd = e.viewport.Update(m)
	return e, cmd
}

// View implements tea.Model.
func (e *Events) View() string {
	if e.loading {
		return e.viewLoading()
	}
	return e.viewEvents()
}

func (e *Events) viewLoading() string {
	content := lipgloss.JoinVertical(lipgloss.Center,
		e.spinner.View(),
		style.MutedText.Render("Loading events..."),
	)
	return lipgloss.Place(e.width, e.height, lipgloss.Center, lipgloss.Center, content)
}

func (e *Events) viewEvents() string {
	header := e.renderHeader()
	tabs := e.renderTabs()
	help := style.HelpBar.Render("←/→: filter • ↑/↓: scroll • esc: back • q: quit")

	headerHeight := lipgloss.Height(header)
	tabsHeight := lipgloss.Height(tabs)
	helpHeight := lipgloss.Height(help)
	viewportHeight := e.height - headerHeight - tabsHeight - helpHeight - 2

	e.viewport.Width = e.width
	e.viewport.Height = viewportHeight

	return lipgloss.JoinVertical(lipgloss.Left,
		header,
		tabs,
		e.viewport.View(),
		help,
	)
}

func (e *Events) renderHeader() string {
	title := fmt.Sprintf(" Events: %s ", e.episodeID)
	count := fmt.Sprintf(" %d events ", len(e.filtered))
	return lipgloss.JoinHorizontal(lipgloss.Top,
		style.Header.Render(title),
		" ",
		style.BadgeInfo.Render(count),
	)
}

func (e *Events) renderTabs() string {
	var tabs []string
	for i, phase := range phaseFilters {
		var tab string
		if i == e.activePhase {
			tab = style.ActiveTab.Render(phase)
		} else {
			tab = style.InactiveTab.Render(phase)
		}
		tabs = append(tabs, tab)
	}
	return lipgloss.JoinHorizontal(lipgloss.Top, tabs...)
}

func (e *Events) renderEvents() string {
	if len(e.filtered) == 0 {
		return style.DimText.Render("No events match the current filter")
	}

	var lines []string
	for _, event := range e.filtered {
		lines = append(lines, e.renderEvent(event))
	}

	return strings.Join(lines, "\n")
}

func (e *Events) renderEvent(event cli.Event) string {
	symbol := style.PhaseSymbol(event.Phase)
	phaseStyle := style.PhaseStyle(event.Phase)
	agent := event.AgentOrDefault()

	// Extract summary from payload
	summary := ""
	if msg := event.PayloadString("message"); msg != "" {
		summary = msg
	} else if task := event.PayloadString("task"); task != "" {
		summary = task
	} else if status := event.PayloadString("status"); status != "" {
		summary = status
	}

	// Truncate summary
	if len(summary) > 60 {
		summary = summary[:57] + "..."
	}

	// Format timestamp
	ts := event.Timestamp
	if len(ts) > 19 {
		ts = ts[:19]
	}

	return fmt.Sprintf("%s %s %s %s",
		style.DimText.Render(ts),
		phaseStyle.Render(symbol+" "+fmt.Sprintf("%-12s", event.Phase)),
		style.MutedText.Render(fmt.Sprintf("%-10s", agent)),
		summary,
	)
}

func (e *Events) applyFilter() {
	if e.activePhase == 0 { // "all"
		e.filtered = e.events
		return
	}

	phase := phaseFilters[e.activePhase]
	e.filtered = nil
	for _, event := range e.events {
		if event.Phase == phase {
			e.filtered = append(e.filtered, event)
		}
	}
}

// SetSize updates the dimensions.
func (e *Events) SetSize(width, height int) {
	e.width = width
	e.height = height
	e.viewport = viewport.New(width, height-8)
	e.viewport.SetContent(e.renderEvents())
}

func (e *Events) fetchEvents() tea.Cmd {
	return func() tea.Msg {
		result, err := e.client.GetEvents(context.Background(), e.episodeID, nil)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.EventsLoaded{
			EpisodeID:  e.episodeID,
			Events:     result.Events,
			EventCount: result.EventCount,
		}
	}
}
