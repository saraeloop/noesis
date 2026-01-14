package proof

import (
	"fmt"
	"sort"
	"strings"

	"noesis.dev/tui/internal/cli"
)

const (
	VerificationVerified   = "VERIFIED"
	VerificationFailed     = "FAILED"
	VerificationUnverified = "UNVERIFIED"

	GovernanceAllowed  = "ALLOWED"
	GovernanceViolated = "VIOLATED"
	GovernanceVetoed   = "VETOED"
	GovernanceAudit    = "AUDIT"

	EvidenceCaptured = "CAPTURED"
	EvidenceMissing  = "MISSING"

	ReplayNotTested = "NOT_TESTED"

	TrustVerified   = "VERIFIED"
	TrustFailed     = "FAILED"
	TrustViolated   = "VIOLATED"
	TrustUnverified = "UNVERIFIED"
)

// Proof summarizes the trust state for an episode run.
type Proof struct {
	EpisodeID string
	Task      string
	StartedAt *string
	Duration  *float64
	Outcome   *string
	Agents    []ObservedAgent
	Reason    string

	Verification string
	Governance   string
	Evidence     string
	Replay       string

	TrustVerdict string

	Assertions   []cli.VerificationAssertion
	PolicyBreach *string
	DiffSummary  string
}

// ObservedAgent summarizes agent activity from events.
type ObservedAgent struct {
	Name        string
	EventCount  int
	PhaseCounts map[string]int
	LastPhase   string
	LastSummary string
}

// NewProofFromViewResult derives a Proof model from a CLI view result.
func NewProofFromViewResult(v *cli.ViewResult) *Proof {
	p := &Proof{
		Verification: VerificationUnverified,
		Governance:   GovernanceAllowed,
		Evidence:     EvidenceMissing,
		Replay:       ReplayNotTested,
		TrustVerdict: TrustUnverified,
		DiffSummary:  "No workspace diff captured",
	}

	if v == nil {
		return p
	}

	p.EpisodeID = v.EpisodeID
	if v.Dashboard.Header.Task != nil {
		p.Task = strings.TrimSpace(*v.Dashboard.Header.Task)
	}
	p.StartedAt = v.Dashboard.Header.StartedAt
	p.Duration = v.Dashboard.Header.Duration
	p.Agents = observedAgentsFromTimeline(v.Dashboard.TimelineRows)

	verification := v.Dashboard.Verification
	p.Assertions = verification.Assertions
	if verification.Outcome.Summary != nil {
		p.Outcome = verification.Outcome.Summary
	} else if verification.Outcome.Status != nil {
		p.Outcome = verification.Outcome.Status
	}

	provided := false
	if verification.Provided != nil {
		provided = *verification.Provided
	} else if verification.Passed != nil || len(verification.Assertions) > 0 {
		provided = true
	}

	if !provided {
		p.Verification = VerificationUnverified
	} else if verificationFailed(verification) {
		p.Verification = VerificationFailed
	} else {
		p.Verification = VerificationVerified
	}

	if verification.WorkspaceDiff != nil {
		p.Evidence = EvidenceCaptured
		p.DiffSummary = summarizeDiff(verification.WorkspaceDiff)
	}

	p.Governance = governanceStatus(v.Dashboard.Header.Governance, verification.Assertions)
	if v.Dashboard.Header.Governance != nil {
		if v.Dashboard.Header.Governance.RuleID != nil {
			p.PolicyBreach = v.Dashboard.Header.Governance.RuleID
		}
	}

	p.TrustVerdict = trustVerdict(p.Governance, p.Verification)
	p.Reason = deriveProofReason(p, verification)
	return p
}

func observedAgentsFromTimeline(rows []cli.TimelineRow) []ObservedAgent {
	agents := map[string]*ObservedAgent{}
	for _, row := range rows {
		name := strings.TrimSpace(row.Agent)
		if name == "" {
			name = "unknown"
		}
		agent := agents[name]
		if agent == nil {
			agent = &ObservedAgent{
				Name:        name,
				PhaseCounts: map[string]int{},
			}
			agents[name] = agent
		}
		agent.EventCount++
		phase := strings.ToLower(strings.TrimSpace(row.Phase))
		if phase != "" {
			agent.PhaseCounts[phase]++
		}
		agent.LastPhase = phase
		agent.LastSummary = strings.TrimSpace(row.Summary)
	}

	out := make([]ObservedAgent, 0, len(agents))
	for _, agent := range agents {
		out = append(out, *agent)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].Name < out[j].Name
	})
	return out
}

func deriveProofReason(p *Proof, verification cli.Verification) string {
	if p.Governance == GovernanceViolated || p.Governance == GovernanceVetoed {
		if p.PolicyBreach != nil && strings.TrimSpace(*p.PolicyBreach) != "" {
			return fmt.Sprintf("Governance breach (%s)", *p.PolicyBreach)
		}
		return "Governance policy violated."
	}
	if verificationFailed(verification) {
		for _, assertion := range verification.Assertions {
			if assertion.Passed {
				continue
			}
			if assertion.Reason != nil && strings.TrimSpace(*assertion.Reason) != "" {
				return *assertion.Reason
			}
			return assertion.Name
		}
		return "Verification failed."
	}
	if verification.Provided == nil || !*verification.Provided {
		return "No verification was provided."
	}
	return "Assertions passed for this run."
}

func verificationFailed(v cli.Verification) bool {
	if v.Passed != nil && !*v.Passed {
		return true
	}
	if v.Error != nil && strings.TrimSpace(*v.Error) != "" {
		return true
	}
	for _, assertion := range v.Assertions {
		if !assertion.Passed {
			return true
		}
	}
	return false
}

func summarizeDiff(diff *cli.WorkspaceDiff) string {
	if diff == nil {
		return ""
	}
	return fmt.Sprintf("+%d ~%d -%d", len(diff.Added), len(diff.Modified), len(diff.Deleted))
}

func governanceStatus(gov *cli.Governance, assertions []cli.VerificationAssertion) string {
	if hasScopeViolation(assertions) {
		return GovernanceViolated
	}
	if gov == nil {
		return GovernanceAllowed
	}

	switch strings.ToUpper(gov.Decision) {
	case "VETO":
		return GovernanceVetoed
	case "AUDIT":
		return GovernanceAudit
	case "ALLOW":
		return GovernanceAllowed
	default:
		return GovernanceAllowed
	}
}

func hasScopeViolation(assertions []cli.VerificationAssertion) bool {
	for _, assertion := range assertions {
		if assertion.Passed {
			continue
		}
		if isScopeAssertion(assertion.Name) {
			return true
		}
	}
	return false
}

func isScopeAssertion(name string) bool {
	switch strings.ToLower(name) {
	case "only_modified",
		"within_paths",
		"no_network",
		"no_secrets",
		"no_write_outside":
		return true
	default:
		return false
	}
}

func trustVerdict(governance, verification string) string {
	if governance == GovernanceViolated || governance == GovernanceVetoed {
		return TrustViolated
	}
	if verification == VerificationFailed {
		return TrustFailed
	}
	if verification == VerificationVerified {
		return TrustVerified
	}
	return TrustUnverified
}
