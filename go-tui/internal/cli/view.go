package cli

// ViewResult is the envelope for `noesis view <id> --json` per ADR-012.
type ViewResult struct {
	Cli        CliVersion        `json:"cli"`
	EpisodeID  string            `json:"episode_id"`
	EpisodeDir string            `json:"episode_dir"`
	Artifacts  map[string]string `json:"artifacts"`
	Dashboard  Dashboard         `json:"dashboard"`
}

// Dashboard is the full episode dashboard view model.
// Matches noesis/cli/view_models.py EpisodeDashboardVM.to_dict()
type Dashboard struct {
	Header           Header           `json:"header"`
	Chips            Chips            `json:"chips"`
	KPIs             KPIs             `json:"kpis"`
	PhaseBreakdown   []PhaseLatency   `json:"phase_breakdown"`
	TimelineRows     []TimelineRow    `json:"timeline_rows"`
	ExecutionMap     ExecutionMap     `json:"execution_map"`
	Verification     Verification     `json:"verification"`
	ValidationIssues []string         `json:"validation_issues"`
	Suggestions      []string         `json:"suggestions"`
}

// Header represents the episode header section.
type Header struct {
	EpisodeID   string      `json:"episode_id"`
	StatusLabel string      `json:"status_label"`
	StartedAt   *string     `json:"started_at"`
	Duration    *float64    `json:"duration"`
	Task        *string     `json:"task"`
	Governance  *Governance `json:"governance"`
}

// Governance represents the governance summary.
type Governance struct {
	Decision string   `json:"decision"` // VETO | AUDIT | ALLOW
	RuleID   *string  `json:"rule_id"`
	Score    *float64 `json:"score"`
	Enforced bool     `json:"enforced"`
}

// Chips represents metadata chips (adapter, planner mode, etc.).
type Chips struct {
	Using       *string `json:"using"`
	PlannerMode *string `json:"planner_mode"`
	DurationStr *string `json:"duration_str"`
	SchemaStr   *string `json:"schema_str"`
}

// KPIs represents key performance indicators.
type KPIs struct {
	SuccessPct    *float64 `json:"success_pct"`
	PlanAdherence *float64 `json:"plan_adherence"`
	VetoCount     *int     `json:"veto_count"`
	ToolCoverage  *float64 `json:"tool_coverage"`
	FirstAction   *string  `json:"first_action"`
}

// PhaseLatency represents timing for a single phase.
type PhaseLatency struct {
	Phase string `json:"phase"`
	Ms    int    `json:"ms"`
}

// TimelineRow represents a single event in the timeline.
type TimelineRow struct {
	DtStr   string `json:"dt_str"`
	Phase   string `json:"phase"`
	Agent   string `json:"agent"`
	Status  string `json:"status"`
	Summary string `json:"summary"`
}

// ExecutionMap represents the 4-phase execution flow.
type ExecutionMap struct {
	Observe ExecutionPhase `json:"observe"`
	Act     ExecutionPhase `json:"act"`
	Verify  ExecutionPhase `json:"verify"`
	Outcome ExecutionPhase `json:"outcome"`
}

// Phases returns all phases in order.
func (e ExecutionMap) Phases() []ExecutionPhase {
	return []ExecutionPhase{e.Observe, e.Act, e.Verify, e.Outcome}
}

// ExecutionPhase represents a single phase status.
type ExecutionPhase struct {
	Phase  string `json:"phase"`  // OBSERVE | ACT | VERIFY | OUTCOME
	Status string `json:"status"` // OK | SKIPPED | ERROR | FAILED | PASSED | VETOED | UNKNOWN
}

// Verification represents the verification section.
type Verification struct {
	AdapterResult *string                 `json:"adapter_result"`
	Outcome       Outcome                 `json:"outcome"`
	Provided      *bool                   `json:"provided"`
	Passed        *bool                   `json:"passed"`
	Error         *string                 `json:"error"`
	Assertions    []VerificationAssertion `json:"assertions"`
	WorkspaceDiff *WorkspaceDiff          `json:"workspace_diff"`
}

// Outcome represents the episode outcome.
type Outcome struct {
	Status  *string `json:"status"`
	Summary *string `json:"summary"`
}

// VerificationAssertion represents a single assertion result.
type VerificationAssertion struct {
	Name   string      `json:"name"`
	Target interface{} `json:"target"` // string | []string
	Passed bool        `json:"passed"`
	Reason *string     `json:"reason"`
}

// WorkspaceDiff represents file changes.
type WorkspaceDiff struct {
	Added    []string `json:"added"`
	Modified []string `json:"modified"`
	Deleted  []string `json:"deleted"`
}
