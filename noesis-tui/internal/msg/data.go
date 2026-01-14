package msg

import (
	"noesis.dev/tui/internal/cli"
	"noesis.dev/tui/internal/ui/proof"
)

// EpisodesLoaded is sent when episode list data has been fetched.
type EpisodesLoaded struct {
	Episodes   []cli.EpisodeRow
	TotalCount int
}

// DashboardLoaded is sent when episode detail data has been fetched.
type DashboardLoaded struct {
	EpisodeID string
	Dashboard cli.Dashboard
	Artifacts map[string]string
}

// EventsLoaded is sent when events data has been fetched.
type EventsLoaded struct {
	EpisodeID  string
	Events     []cli.Event
	EventCount int
}

// RunComplete is sent when a run has finished.
type RunComplete struct {
	Result *cli.RunResult
}

// AgentSummary describes observed agent activity.
type AgentSummary struct {
	Name        string
	EventCount  int
	PhaseCounts map[string]int
}

// AgentSummaryLoaded is sent when agent summary data has been fetched.
type AgentSummaryLoaded struct {
	EpisodeID string
	Agents    []AgentSummary
}

// ProofReasonLoaded is sent when a proof reason has been fetched.
type ProofReasonLoaded struct {
	EpisodeID string
	Reason    string
}

// ChangesLoaded is sent when diff data has been fetched.
type ChangesLoaded struct {
	EpisodeID string
	Diff      *cli.WorkspaceDiff
}

// ProofLoaded is sent when proof data has been fetched.
type ProofLoaded struct {
	EpisodeID     string
	Proof         *proof.Proof
	WorkspaceDiff *cli.WorkspaceDiff
}

// Error is sent when an operation fails.
type Error struct {
	Err error
}

func (e Error) Error() string {
	return e.Err.Error()
}
