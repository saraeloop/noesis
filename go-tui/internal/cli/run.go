package cli

// RunResult is the envelope for `noesis run "task" --json` per ADR-011.
type RunResult struct {
	Cli                  CliVersion        `json:"cli"`
	EpisodeID            string            `json:"episode_id"`
	EpisodeDir           string            `json:"episode_dir"`
	Artifacts            map[string]string `json:"artifacts"`
	SummarySchemaVersion string            `json:"summary_schema_version"`
	Outcome              *string           `json:"outcome"`
	AdapterResult        *string           `json:"adapter_result"`
	Verification         RunVerification   `json:"verification"`
	Capabilities         []string          `json:"capabilities"`
	Invocation           RunInvocation     `json:"invocation"`
}

// RunVerification is the verification summary from run.
type RunVerification struct {
	Provided *bool   `json:"provided"`
	Passed   *bool   `json:"passed"`
	Error    *string `json:"error"`
}

// RunInvocation captures how the run was invoked.
type RunInvocation struct {
	Argv           []string `json:"argv"`
	VerifyProvided bool     `json:"verify_provided"`
	Workspace      *string  `json:"workspace"`
}

// OutcomeOrDefault returns the outcome value or "unknown" if nil.
func (r RunResult) OutcomeOrDefault() string {
	if r.Outcome != nil {
		return *r.Outcome
	}
	return "unknown"
}

// IsSuccess returns whether the run was successful.
func (r RunResult) IsSuccess() bool {
	outcome := r.OutcomeOrDefault()
	return outcome == "success" || outcome == "success_unverified"
}

// HasCapability checks if the run has a specific capability.
func (r RunResult) HasCapability(cap string) bool {
	for _, c := range r.Capabilities {
		if c == cap {
			return true
		}
	}
	return false
}
