package model

import (
	"context"
	"fmt"
	"strings"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"

	"github.com/charmbracelet/bubbles/help"
	"github.com/charmbracelet/bubbles/key"
	"github.com/charmbracelet/bubbles/viewport"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// Changes renders a scrollable diff view for a single episode.
type Changes struct {
	episodeID string
	diff      *cli.WorkspaceDiff
	loading   bool
	viewport  viewport.Model
	help      help.Model
	keyMap    changesKeyMap
	client    *cli.Client
	width     int
	height    int
	header    string
	footer    string
}

// NewChanges creates a new Changes model.
func NewChanges(client *cli.Client, episodeID string) *Changes {
	h := help.New()
	h.ShowAll = false

	return &Changes{
		episodeID: episodeID,
		loading:   true,
		client:    client,
		help:      h,
		keyMap:    newChangesKeyMap(),
	}
}

// Init implements tea.Model.
func (c *Changes) Init() tea.Cmd {
	return c.fetchDiff()
}

// Update implements tea.Model.
func (c *Changes) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case tea.WindowSizeMsg:
		c.width = m.Width
		c.height = m.Height
		c.reflow()
		return c, nil

	case msg.ChangesLoaded:
		c.loading = false
		c.diff = m.Diff
		c.reflow()
		return c, nil

	case msg.Error:
		c.loading = false
		return c, nil
	}

	if !c.loading {
		var cmd tea.Cmd
		c.viewport, cmd = c.viewport.Update(m)
		return c, cmd
	}

	return c, nil
}

// View implements tea.Model.
func (c *Changes) View() string {
	if c.loading {
		return style.MutedText.Render("Loading changes...")
	}

	return lipgloss.JoinVertical(lipgloss.Left,
		c.header,
		c.viewport.View(),
		c.footer,
	)
}

// SetSize sets the window size.
func (c *Changes) SetSize(width, height int) {
	c.width = width
	c.height = height
	c.reflow()
}

func (c *Changes) reflow() {
	if c.width == 0 || c.height == 0 {
		return
	}
	c.header = c.renderHeader()
	c.footer = style.HelpBar.Render(c.help.View(c.keyMap))

	headerH := lipgloss.Height(c.header)
	footerH := lipgloss.Height(c.footer)
	viewportHeight := c.height - headerH - footerH
	if viewportHeight < 1 {
		viewportHeight = 1
	}

	c.viewport.Width = style.DetectBreakpoint(c.width).ContentWidth(c.width)
	c.viewport.Height = viewportHeight
	c.viewport.SetContent(c.renderContent())
}

func (c *Changes) renderHeader() string {
	summary := "No diff available"
	if c.diff != nil {
		summary = fmt.Sprintf("%d added, %d modified, %d deleted", len(c.diff.Added), len(c.diff.Modified), len(c.diff.Deleted))
	}
	return lipgloss.JoinVertical(lipgloss.Left,
		style.Title.Render("Changes"),
		style.MutedText.Render(summary),
	)
}

func (c *Changes) renderContent() string {
	if c.diff == nil {
		return style.MutedText.Render("No diff available for this run.")
	}

	iconSet := style.Icons()
	sections := []string{
		renderDiffSection("Added", c.diff.Added, iconSet.FileAdded(), style.SuccessText),
		renderDiffSection("Modified", c.diff.Modified, iconSet.FileModified(), style.WarningText),
		renderDiffSection("Deleted", c.diff.Deleted, iconSet.FileDeleted(), style.ErrorText),
	}
	return lipgloss.JoinVertical(lipgloss.Left, sections...)
}

func renderDiffSection(title string, items []string, icon string, textStyle lipgloss.Style) string {
	if len(items) == 0 {
		return lipgloss.JoinVertical(lipgloss.Left,
			style.Subtitle.Render(title),
			style.MutedText.Render("  None"),
		)
	}
	lines := make([]string, 0, len(items))
	for _, item := range items {
		lines = append(lines, fmt.Sprintf("  %s %s", textStyle.Render(icon), item))
	}
	return lipgloss.JoinVertical(lipgloss.Left, style.Subtitle.Render(title), strings.Join(lines, "\n"))
}

func (c *Changes) fetchDiff() tea.Cmd {
	return func() tea.Msg {
		result, err := c.client.ViewEpisode(context.Background(), c.episodeID)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.ChangesLoaded{
			EpisodeID: c.episodeID,
			Diff:      result.Dashboard.Verification.WorkspaceDiff,
		}
	}
}

type changesKeyMap struct {
	Back key.Binding
}

func newChangesKeyMap() changesKeyMap {
	return changesKeyMap{
		Back: key.NewBinding(
			key.WithKeys("esc"),
			key.WithHelp("esc", "back"),
		),
	}
}

func (k changesKeyMap) ShortHelp() []key.Binding {
	return []key.Binding{k.Back}
}

func (k changesKeyMap) FullHelp() [][]key.Binding {
	return [][]key.Binding{{k.Back}}
}
