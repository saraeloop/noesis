// Package msg defines Bubbletea message types for the Noesis TUI.
package msg

// Screen represents the different screens in the TUI.
type Screen int

const (
	ScreenHome Screen = iota
	ScreenDetail
	ScreenEvents
	ScreenRun
)

// String returns the screen name.
func (s Screen) String() string {
	switch s {
	case ScreenHome:
		return "home"
	case ScreenDetail:
		return "detail"
	case ScreenEvents:
		return "events"
	case ScreenRun:
		return "run"
	default:
		return "unknown"
	}
}

// NavigateTo is a message to navigate to a different screen.
type NavigateTo struct {
	Screen  Screen
	Payload interface{} // e.g., episode ID for detail/events screens
}

// GoBack is a message to navigate back to the previous screen.
type GoBack struct{}
