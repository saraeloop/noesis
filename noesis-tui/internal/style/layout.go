package style

// Breakpoint represents terminal width breakpoints.
type Breakpoint int

const (
	Compact  Breakpoint = iota // < 60 cols
	Standard                   // 60-99 cols
	Wide                       // >= 100 cols
)

// Breakpoint thresholds
const (
	CompactMax  = 60
	StandardMax = 100
)

// DetectBreakpoint returns the breakpoint for a given width.
func DetectBreakpoint(width int) Breakpoint {
	if width < CompactMax {
		return Compact
	}
	if width < StandardMax {
		return Standard
	}
	return Wide
}

// Layout constants
const (
	// Padding and margins
	PanelPaddingV = 1
	PanelPaddingH = 2
	Gutter        = 2
	Indent        = 2

	// Column widths
	PanelWidth      = 88
	MaxWidth        = 100
	MinWidth        = 40
	CommandColWidth = 14
	DescColWidth    = 40

	// List dimensions
	EpisodeIDWidth   = 12
	StatusColWidth   = 10
	OutcomeColWidth  = 20
	DurationColWidth = 8
)

// String returns the breakpoint name.
func (b Breakpoint) String() string {
	switch b {
	case Compact:
		return "compact"
	case Standard:
		return "standard"
	case Wide:
		return "wide"
	default:
		return "unknown"
	}
}

// ContentWidth returns the appropriate content width for a breakpoint.
func (b Breakpoint) ContentWidth(termWidth int) int {
	switch b {
	case Compact:
		return max(termWidth-4, MinWidth)
	case Standard:
		return min(termWidth-4, PanelWidth)
	case Wide:
		return min(termWidth-4, MaxWidth)
	default:
		return termWidth - 4
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func max(a, b int) int {
	if a > b {
		return a
	}
	return b
}
