package msg

import "noesis.dev/tui/internal/cli"

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

// Error is sent when an operation fails.
type Error struct {
	Err error
}

func (e Error) Error() string {
	return e.Err.Error()
}
