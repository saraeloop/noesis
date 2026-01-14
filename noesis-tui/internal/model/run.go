package model

import (
	"context"

	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"

	"github.com/charmbracelet/bubbles/spinner"
	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// RunState represents the state of the run screen.
type RunState int

const (
	RunStateInput RunState = iota
	RunStateRunning
	RunStateComplete
)

// Run is the run launcher screen model.
type Run struct {
	state     RunState
	taskInput textinput.Model
	spinner   spinner.Model
	result    *cli.RunResult
	err       error
	client    *cli.Client
	width     int
	height    int
}

// NewRun creates a new Run model.
func NewRun(client *cli.Client) *Run {
	ti := textinput.New()
	ti.Placeholder = "Enter task description..."
	ti.Focus()
	ti.Width = 60
	ti.CharLimit = 500

	s := spinner.New()
	s.Spinner = spinner.Pulse
	s.Style = lipgloss.NewStyle().Foreground(style.AccentColor)

	return &Run{
		state:     RunStateInput,
		taskInput: ti,
		spinner:   s,
		client:    client,
	}
}

// Init implements tea.Model.
func (r *Run) Init() tea.Cmd {
	return textinput.Blink
}

// Update implements tea.Model.
func (r *Run) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case msg.RunComplete:
		r.state = RunStateComplete
		r.result = m.Result
		return r, nil

	case msg.Error:
		r.state = RunStateComplete
		r.err = m.Err
		return r, nil

	case tea.KeyMsg:
		switch r.state {
		case RunStateInput:
			switch m.String() {
			case "enter":
				if r.taskInput.Value() != "" {
					r.state = RunStateRunning
					return r, tea.Batch(
						r.spinner.Tick,
						r.runEpisode(),
					)
				}
			}
		case RunStateComplete:
			switch m.String() {
			case "enter":
				if r.result != nil {
					return r, func() tea.Msg {
						return msg.NavigateTo{Screen: msg.ScreenDetail, Payload: r.result.EpisodeID}
					}
				}
			case "n":
				// Start a new run
				r.state = RunStateInput
				r.taskInput.SetValue("")
				r.taskInput.Focus()
				r.result = nil
				r.err = nil
				return r, textinput.Blink
			}
		}
	}

	var cmd tea.Cmd
	switch r.state {
	case RunStateInput:
		r.taskInput, cmd = r.taskInput.Update(m)
	case RunStateRunning:
		r.spinner, cmd = r.spinner.Update(m)
	}
	return r, cmd
}

// View implements tea.Model.
func (r *Run) View() string {
	switch r.state {
	case RunStateInput:
		return r.viewInput()
	case RunStateRunning:
		return r.viewRunning()
	case RunStateComplete:
		return r.viewComplete()
	}
	return ""
}

func (r *Run) viewInput() string {
	title := style.Title.Render("New Episode")
	prompt := style.Subtitle.Render("Task:")
	input := r.taskInput.View()
	help := style.HelpBar.Render("enter: run • esc: cancel")

	content := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		prompt,
		input,
		"",
		help,
	)

	return lipgloss.Place(r.width, r.height, lipgloss.Center, lipgloss.Center, content)
}

func (r *Run) viewRunning() string {
	task := r.taskInput.Value()
	if len(task) > 50 {
		task = task[:47] + "..."
	}

	content := lipgloss.JoinVertical(lipgloss.Center,
		r.spinner.View(),
		"",
		style.MutedText.Render("Running episode..."),
		style.DimText.Render(task),
	)

	return lipgloss.Place(r.width, r.height, lipgloss.Center, lipgloss.Center, content)
}

func (r *Run) viewComplete() string {
	if r.err != nil {
		return r.viewError()
	}
	return r.viewSuccess()
}

func (r *Run) viewError() string {
	title := style.ErrorText.Render("Episode Failed")
	errMsg := style.DimText.Render(r.err.Error())
	help := style.HelpBar.Render("n: new run • esc: back")

	content := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		errMsg,
		"",
		help,
	)

	return lipgloss.Place(r.width, r.height, lipgloss.Center, lipgloss.Center, content)
}

func (r *Run) viewSuccess() string {
	if r.result == nil {
		return ""
	}

	outcome := r.result.OutcomeOrDefault()
	badge := style.GetOutcomeBadge(outcome)

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

	title := style.SuccessText.Render("Episode Complete")
	episodeID := style.Subtitle.Render("Episode: " + r.result.EpisodeID)
	outcomeBadge := badgeStyle.Render(badge.Label)
	help := style.HelpBar.Render("enter: view details • n: new run • esc: back")

	content := lipgloss.JoinVertical(lipgloss.Left,
		title,
		"",
		episodeID,
		outcomeBadge,
		"",
		help,
	)

	return lipgloss.Place(r.width, r.height, lipgloss.Center, lipgloss.Center, content)
}

// SetSize updates the dimensions.
func (r *Run) SetSize(width, height int) {
	r.width = width
	r.height = height
	r.taskInput.Width = min(60, width-10)
}

func (r *Run) runEpisode() tea.Cmd {
	task := r.taskInput.Value()
	return func() tea.Msg {
		result, err := r.client.RunEpisode(context.Background(), task)
		if err != nil {
			return msg.Error{Err: err}
		}
		return msg.RunComplete{Result: result}
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
