// Package model contains the Bubbletea models for the Noesis TUI.
package model

import (
	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/msg"
	"noesis.dev/tui/internal/style"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

// App is the root Bubbletea model that manages screen routing.
type App struct {
	// Screen state
	screen     msg.Screen
	prevScreen msg.Screen

	// Screen models
	home    *Home
	detail  *Detail
	events  *Events
	run     *Run
	proof   *ProofModel
	browse  *Browse
	changes *Changes

	// Shared state
	client    *cli.Client
	lastError error

	// Window dimensions
	width  int
	height int
}

// NewApp creates a new App model.
func NewApp() *App {
	client := cli.NewClient()
	return &App{
		screen: msg.ScreenHome,
		client: client,
		home:   NewHome(client),
	}
}

// Init implements tea.Model.
func (a *App) Init() tea.Cmd {
	return a.home.Init()
}

// Update implements tea.Model.
func (a *App) Update(m tea.Msg) (tea.Model, tea.Cmd) {
	switch m := m.(type) {
	case tea.WindowSizeMsg:
		a.width = m.Width
		a.height = m.Height
		// Propagate size to current screen and delegate the message
		a.propagateSize(m)
		return a.delegateToScreen(m)

	case tea.KeyMsg:
		switch m.String() {
		case "ctrl+c":
			return a, tea.Quit
		case "q":
			if a.screen == msg.ScreenHome {
				return a, tea.Quit
			}
			// Navigate back
			return a.navigateBack()
		case "esc":
			if a.screen != msg.ScreenHome {
				return a.navigateBack()
			}
		}

	case msg.NavigateTo:
		return a.navigateTo(m.Screen, m.Payload)

	case msg.GoBack:
		return a.navigateBack()

	case msg.Error:
		a.lastError = m.Err
	}

	// Delegate to current screen
	return a.delegateToScreen(m)
}

// View implements tea.Model.
func (a *App) View() string {
	var content string

	switch a.screen {
	case msg.ScreenHome:
		if a.home != nil {
			content = a.home.View()
		}
	case msg.ScreenDetail:
		if a.detail != nil {
			content = a.detail.View()
		}
	case msg.ScreenEvents:
		if a.events != nil {
			content = a.events.View()
		}
	case msg.ScreenRun:
		if a.run != nil {
			content = a.run.View()
		}
	case msg.ScreenProof:
		if a.proof != nil {
			content = a.proof.View()
		}
	case msg.ScreenBrowse:
		if a.browse != nil {
			content = a.browse.View()
		}
	case msg.ScreenChanges:
		if a.changes != nil {
			content = a.changes.View()
		}
	}

	// Add error display if present
	if a.lastError != nil {
		errorBar := style.ErrorText.Render("Error: " + a.lastError.Error())
		content = lipgloss.JoinVertical(lipgloss.Left, content, errorBar)
	}

	return content
}

// navigateTo switches to a different screen.
func (a *App) navigateTo(screen msg.Screen, payload interface{}) (tea.Model, tea.Cmd) {
	a.prevScreen = a.screen
	a.screen = screen
	a.lastError = nil

	switch screen {
	case msg.ScreenHome:
		if a.home == nil {
			a.home = NewHome(a.client)
		}
		a.home.SetSize(a.width, a.height)
		return a, a.home.Init()

	case msg.ScreenDetail:
		episodeID, _ := payload.(string)
		a.detail = NewDetail(a.client, episodeID)
		a.detail.SetSize(a.width, a.height)
		return a, a.detail.Init()

	case msg.ScreenEvents:
		episodeID, _ := payload.(string)
		a.events = NewEvents(a.client, episodeID)
		a.events.SetSize(a.width, a.height)
		return a, a.events.Init()

	case msg.ScreenRun:
		a.run = NewRun(a.client)
		a.run.SetSize(a.width, a.height)
		return a, a.run.Init()
	case msg.ScreenProof:
		episodeID, _ := payload.(string)
		a.proof = NewProofModel(a.client, episodeID)
		a.proof.SetSize(a.width, a.height)
		return a, a.proof.Init()
	case msg.ScreenBrowse:
		a.browse = NewBrowse(a.client)
		a.browse.SetSize(a.width, a.height)
		return a, a.browse.Init()
	case msg.ScreenChanges:
		episodeID, _ := payload.(string)
		a.changes = NewChanges(a.client, episodeID)
		a.changes.SetSize(a.width, a.height)
		return a, a.changes.Init()
	}

	return a, nil
}

// navigateBack returns to the previous screen.
func (a *App) navigateBack() (tea.Model, tea.Cmd) {
	return a.navigateTo(msg.ScreenHome, nil)
}

// propagateSize sends window size to the current screen.
func (a *App) propagateSize(m tea.WindowSizeMsg) {
	switch a.screen {
	case msg.ScreenHome:
		if a.home != nil {
			a.home.SetSize(m.Width, m.Height)
		}
	case msg.ScreenDetail:
		if a.detail != nil {
			a.detail.SetSize(m.Width, m.Height)
		}
	case msg.ScreenEvents:
		if a.events != nil {
			a.events.SetSize(m.Width, m.Height)
		}
	case msg.ScreenRun:
		if a.run != nil {
			a.run.SetSize(m.Width, m.Height)
		}
	case msg.ScreenProof:
		if a.proof != nil {
			a.proof.SetSize(m.Width, m.Height)
		}
	case msg.ScreenBrowse:
		if a.browse != nil {
			a.browse.SetSize(m.Width, m.Height)
		}
	case msg.ScreenChanges:
		if a.changes != nil {
			a.changes.SetSize(m.Width, m.Height)
		}
	}
}

// delegateToScreen routes messages to the current screen.
func (a *App) delegateToScreen(m tea.Msg) (tea.Model, tea.Cmd) {
	switch a.screen {
	case msg.ScreenHome:
		if a.home != nil {
			model, cmd := a.home.Update(m)
			a.home = model.(*Home)
			return a, cmd
		}
	case msg.ScreenDetail:
		if a.detail != nil {
			model, cmd := a.detail.Update(m)
			a.detail = model.(*Detail)
			return a, cmd
		}
	case msg.ScreenEvents:
		if a.events != nil {
			model, cmd := a.events.Update(m)
			a.events = model.(*Events)
			return a, cmd
		}
	case msg.ScreenRun:
		if a.run != nil {
			model, cmd := a.run.Update(m)
			a.run = model.(*Run)
			return a, cmd
		}
	case msg.ScreenProof:
		if a.proof != nil {
			model, cmd := a.proof.Update(m)
			a.proof = model.(*ProofModel)
			return a, cmd
		}
	case msg.ScreenBrowse:
		if a.browse != nil {
			model, cmd := a.browse.Update(m)
			a.browse = model.(*Browse)
			return a, cmd
		}
	case msg.ScreenChanges:
		if a.changes != nil {
			model, cmd := a.changes.Update(m)
			a.changes = model.(*Changes)
			return a, cmd
		}
	}
	return a, nil
}
