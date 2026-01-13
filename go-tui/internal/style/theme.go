// Package style provides Lipgloss styling for the Noesis TUI.
package style

import "github.com/charmbracelet/lipgloss"

// Colors matching noesis/cli/theme.py
var (
	// Brand colors
	BrandColor  = lipgloss.Color("#C084FC") // bright_magenta
	AccentColor = lipgloss.Color("#38BDF8") // bright_cyan

	// Status colors
	SuccessColor = lipgloss.Color("#4ADE80") // bright_green
	WarningColor = lipgloss.Color("#FACC15") // bright_yellow
	ErrorColor   = lipgloss.Color("#F87171") // bright_red
	InfoColor    = lipgloss.Color("#60A5FA") // bright_blue

	// Neutral colors
	MutedColor = lipgloss.Color("#9CA3AF") // bright_black / gray
	DimColor   = lipgloss.Color("#6B7280") // darker gray
	TextColor  = lipgloss.Color("#E5E7EB") // light gray / white
	BGColor    = lipgloss.Color("#1F2937") // dark background
)

// Text styles
var (
	Title = lipgloss.NewStyle().
		Bold(true).
		Foreground(BrandColor)

	BrandStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(BrandColor)

	Subtitle = lipgloss.NewStyle().
			Bold(true).
			Foreground(AccentColor)

	MutedText = lipgloss.NewStyle().
			Foreground(MutedColor)

	DimText = lipgloss.NewStyle().
		Foreground(DimColor)

	SuccessText = lipgloss.NewStyle().
			Bold(true).
			Foreground(SuccessColor)

	WarningText = lipgloss.NewStyle().
			Foreground(WarningColor)

	ErrorText = lipgloss.NewStyle().
			Bold(true).
			Foreground(ErrorColor)

	InfoText = lipgloss.NewStyle().
			Foreground(InfoColor)
)

// Status-specific styles
var (
	StatusSuccess = lipgloss.NewStyle().
			Bold(true).
			Foreground(SuccessColor)

	StatusVetoed = lipgloss.NewStyle().
			Bold(true).
			Foreground(ErrorColor)

	StatusAudit = lipgloss.NewStyle().
			Bold(true).
			Foreground(WarningColor)

	StatusError = lipgloss.NewStyle().
			Bold(true).
			Foreground(ErrorColor)

	StatusPending = lipgloss.NewStyle().
			Foreground(MutedColor)

	StatusSkipped = lipgloss.NewStyle().
			Foreground(MutedColor)
)

// Panel and container styles
var (
	Panel = lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(MutedColor).
		Padding(1, 2)

	SelectedPanel = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(AccentColor).
			Padding(1, 2)

	Header = lipgloss.NewStyle().
		Bold(true).
		Background(BrandColor).
		Foreground(lipgloss.Color("#FFFFFF")).
		Padding(0, 2)

	HelpBar = lipgloss.NewStyle().
		Foreground(MutedColor).
		Padding(0, 1)
)

// Badge styles
var (
	BadgeSuccess = lipgloss.NewStyle().
			Bold(true).
			Background(SuccessColor).
			Foreground(lipgloss.Color("#FFFFFF")).
			Padding(0, 1)

	BadgeWarning = lipgloss.NewStyle().
			Bold(true).
			Background(WarningColor).
			Foreground(lipgloss.Color("#000000")).
			Padding(0, 1)

	BadgeError = lipgloss.NewStyle().
			Bold(true).
			Background(ErrorColor).
			Foreground(lipgloss.Color("#FFFFFF")).
			Padding(0, 1)

	BadgeInfo = lipgloss.NewStyle().
			Bold(true).
			Background(InfoColor).
			Foreground(lipgloss.Color("#FFFFFF")).
			Padding(0, 1)

	BadgeMuted = lipgloss.NewStyle().
			Background(MutedColor).
			Foreground(lipgloss.Color("#FFFFFF")).
			Padding(0, 1)
)

// Tab styles
var (
	ActiveTab = lipgloss.NewStyle().
			Bold(true).
			Foreground(AccentColor).
			Border(lipgloss.NormalBorder(), false, false, true, false).
			BorderForeground(AccentColor).
			Padding(0, 2)

	InactiveTab = lipgloss.NewStyle().
			Foreground(MutedColor).
			Padding(0, 2)
)

// Phase colors for timeline
var PhaseColors = map[string]lipgloss.Color{
	"start":      AccentColor,
	"observe":    InfoColor,
	"intuition":  BrandColor,
	"interpret":  InfoColor,
	"plan":       AccentColor,
	"governance": WarningColor,
	"direction":  InfoColor,
	"insight":    SuccessColor,
	"reason":     MutedColor,
	"act":        TextColor,
	"reflect":    SuccessColor,
	"learn":      AccentColor,
	"memory":     MutedColor,
	"terminate":  WarningColor,
	"error":      ErrorColor,
}

// PhaseStyle returns a style for a specific phase.
func PhaseStyle(phase string) lipgloss.Style {
	if color, ok := PhaseColors[phase]; ok {
		return lipgloss.NewStyle().Foreground(color)
	}
	return MutedText
}
