package cli

// PsResult is the envelope for `noesis ps --json` per ADR-012.
type PsResult struct {
	Cli        CliVersion   `json:"cli"`
	Episodes   []EpisodeRow `json:"episodes"`
	TotalCount int          `json:"total_count"`
	Limit      int          `json:"limit"`
	Offset     int          `json:"offset"`
}

// EpisodeRow represents a single episode in the list view.
type EpisodeRow struct {
	EpisodeID    string  `json:"episode_id"`
	EpisodeShort string  `json:"episode_short"`
	Status       string  `json:"status"`
	StatusRaw    *string `json:"status_raw,omitempty"`
	Outcome      *string `json:"outcome,omitempty"`
	Success      *bool   `json:"success,omitempty"`
	Using        *string `json:"using,omitempty"`
	Task         string  `json:"task"`
	StartedAt    string  `json:"started_at"`
	Duration     string  `json:"duration"`
}

// OutcomeOrDefault returns the outcome value or "unknown" if nil.
func (e EpisodeRow) OutcomeOrDefault() string {
	if e.Outcome != nil {
		return *e.Outcome
	}
	return "unknown"
}

// IsSuccess returns whether the episode was successful.
func (e EpisodeRow) IsSuccess() bool {
	if e.Success != nil {
		return *e.Success
	}
	outcome := e.OutcomeOrDefault()
	return outcome == "success" || outcome == "success_unverified"
}
