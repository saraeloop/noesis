package style

// StatusSymbols maps status strings to Unicode symbols.
// Matches noesis/cli/theme.py STATUS_SYMBOLS
var StatusSymbols = map[string]string{
	"SUCCESS":  "●",
	"OK":       "●",
	"VETOED":   "✗",
	"VETO":     "✗",
	"AUDIT":    "⚠",
	"ERROR":    "✗",
	"PENDING":  "○",
	"UNKNOWN":  "○",
	"PASSED":   "✓",
	"FAILED":   "✗",
	"SKIPPED":  "○",
	"ALLOW":    "●",
}

// PhaseSymbols maps phase names to Unicode symbols.
// Matches noesis/cli/theme.py PHASE_SYMBOLS
var PhaseSymbols = map[string]string{
	"start":      "◆",
	"observe":    "○",
	"intuition":  "◇",
	"interpret":  "◈",
	"plan":       "▸",
	"governance": "◈",
	"direction":  "→",
	"act":        "●",
	"reflect":    "↺",
	"learn":      "◆",
	"insight":    "◇",
	"memory":     "◆",
	"terminate":  "■",
	"error":      "✗",
}

// Navigation symbols
const (
	NavArrow = "→"
	Bullet   = "•"
	Diamond  = "◆"
	Check    = "✓"
	Cross    = "✗"
	Warning  = "⚠"
	Dot      = "●"
	Circle   = "○"
)

// StatusSymbol returns the symbol for a status string.
func StatusSymbol(status string) string {
	if sym, ok := StatusSymbols[status]; ok {
		return sym
	}
	return "○"
}

// PhaseSymbol returns the symbol for a phase name.
func PhaseSymbol(phase string) string {
	if sym, ok := PhaseSymbols[phase]; ok {
		return sym
	}
	return "○"
}

// OutcomeBadge represents visual metadata for an outcome.
type OutcomeBadge struct {
	Label  string
	Symbol string
	Style  string // "ok" | "warn" | "err" | "muted"
}

// OutcomeBadges maps outcome values to badge metadata.
// Matches noesis/cli/theme.py _OUTCOME_BADGES
var OutcomeBadges = map[string]OutcomeBadge{
	"success":            {Label: "SUCCESS", Symbol: "●", Style: "ok"},
	"success_unverified": {Label: "SUCCESS", Symbol: "○", Style: "ok"},
	"goal_not_achieved":  {Label: "GOAL NOT ACHIEVED", Symbol: "●", Style: "err"},
	"vetoed":             {Label: "VETOED", Symbol: "●", Style: "warn"},
	"violated":           {Label: "VIOLATED", Symbol: "●", Style: "err"},
	"error":              {Label: "ERROR", Symbol: "●", Style: "err"},
}

// GetOutcomeBadge returns the badge for an outcome value.
func GetOutcomeBadge(outcome string) OutcomeBadge {
	if badge, ok := OutcomeBadges[outcome]; ok {
		return badge
	}
	return OutcomeBadge{Label: "UNKNOWN", Symbol: "●", Style: "muted"}
}
