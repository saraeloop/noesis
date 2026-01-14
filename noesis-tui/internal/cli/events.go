package cli

// EventsResult is the envelope for `noesis events <id> --envelope` per ADR-012.
type EventsResult struct {
	Cli        CliVersion   `json:"cli"`
	EpisodeID  string       `json:"episode_id"`
	Events     []Event      `json:"events"`
	Filters    EventFilters `json:"filters"`
	EventCount int          `json:"event_count"`
}

// EventFilters represents the applied filters.
type EventFilters struct {
	Phase *string `json:"phase"`
}

// Event represents a single cognitive event.
type Event struct {
	ID        string                 `json:"id,omitempty"`
	EpisodeID string                 `json:"episode_id,omitempty"`
	Phase     string                 `json:"phase"`
	AgentID   *string                `json:"agent_id,omitempty"`
	Payload   map[string]interface{} `json:"payload"`
	CausedBy  *string                `json:"caused_by,omitempty"`
	Timestamp string                 `json:"timestamp"`
	Metrics   *EventMetrics          `json:"metrics,omitempty"`
}

// EventMetrics represents event timing.
type EventMetrics struct {
	StartedAt   string  `json:"started_at"`
	CompletedAt string  `json:"completed_at"`
	DurationMs  float64 `json:"duration_ms"`
}

// AgentOrDefault returns the agent ID or "system" if nil.
func (e Event) AgentOrDefault() string {
	if e.AgentID != nil {
		return *e.AgentID
	}
	return "system"
}

// PayloadString extracts a string value from payload, returning empty string if not found.
func (e Event) PayloadString(key string) string {
	if v, ok := e.Payload[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
	}
	return ""
}
