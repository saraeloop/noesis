package style

import (
	"os"
	"strings"
)

// IconSet defines the icon contract for the TUI.
type IconSet interface {
	Verified() string
	Failed() string
	Violated() string
	Evidence() string
	Governance() string
	Replay() string
	FileAdded() string
	FileModified() string
	FileDeleted() string
}

// UnicodeIcons is the default icon set.
type UnicodeIcons struct{}

func (UnicodeIcons) Verified() string     { return "✓" }
func (UnicodeIcons) Failed() string       { return "✗" }
func (UnicodeIcons) Violated() string     { return "⚠" }
func (UnicodeIcons) Evidence() string     { return "●" }
func (UnicodeIcons) Governance() string   { return "●" }
func (UnicodeIcons) Replay() string       { return "●" }
func (UnicodeIcons) FileAdded() string    { return "+" }
func (UnicodeIcons) FileModified() string { return "~" }
func (UnicodeIcons) FileDeleted() string  { return "-" }

// NerdIcons uses Nerd Font Codicons.
type NerdIcons struct{}

func (NerdIcons) Verified() string     { return "" }
func (NerdIcons) Failed() string       { return "" }
func (NerdIcons) Violated() string     { return "" }
func (NerdIcons) Evidence() string     { return "" }
func (NerdIcons) Governance() string   { return "" }
func (NerdIcons) Replay() string       { return "" }
func (NerdIcons) FileAdded() string    { return "" }
func (NerdIcons) FileModified() string { return "" }
func (NerdIcons) FileDeleted() string  { return "" }

// Icons returns the active icon set based on NOESIS_ICONS.
func Icons() IconSet {
	if strings.EqualFold(strings.TrimSpace(os.Getenv("NOESIS_ICONS")), "nerd") {
		return NerdIcons{}
	}
	return UnicodeIcons{}
}
