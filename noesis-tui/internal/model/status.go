package model

import (
	"strings"

	"noesis.dev/tui/internal/cli"
)

type EpisodeBucket string

const (
	BucketOK           EpisodeBucket = "ok"
	BucketBlocked      EpisodeBucket = "blocked"
	BucketAudit        EpisodeBucket = "audit"
	BucketVerifyFailed EpisodeBucket = "verify_failed"
	BucketError        EpisodeBucket = "error"
	BucketUnverified   EpisodeBucket = "unverified"
	BucketUnknown      EpisodeBucket = "unknown"
)

type EpisodeStatus struct {
	Label      string
	Severity   string // ok | warn | err | muted
	OutcomeKey string
	Bucket     EpisodeBucket
}

// classifyEpisode maps summary-derived fields to a UI status.
// Source of truth order:
// 1) summary.status / status_raw for terminal states (vetoed, error).
// 2) summary.outcome for verification-driven outcomes (goal_not_achieved, success_unverified, success).
// 3) flags.governance_mode + veto_count for audit/veto hints when available.
func classifyEpisode(ep cli.EpisodeRow) EpisodeStatus {
	outcome := strings.ToLower(strings.TrimSpace(ep.OutcomeOrDefault()))
	status := strings.ToLower(strings.TrimSpace(ep.Status))
	statusRaw := strings.ToLower(strings.TrimSpace(derefString(ep.StatusRaw)))
	govMode := flagString(ep.Flags, "governance_mode")
	vetoCount := derefInt(ep.VetoCount)

	if status == "vetoed" || statusRaw == "vetoed" || outcome == "vetoed" || (vetoCount > 0 && govMode == "enforce") {
		return EpisodeStatus{Label: "VETOED", Severity: "warn", OutcomeKey: "vetoed", Bucket: BucketBlocked}
	}

	if govMode == "audit" {
		return EpisodeStatus{Label: "AUDIT", Severity: "warn", OutcomeKey: "audit", Bucket: BucketAudit}
	}

	if outcome == "goal_not_achieved" {
		return EpisodeStatus{Label: "VERIFY FAILED", Severity: "err", OutcomeKey: "goal_not_achieved", Bucket: BucketVerifyFailed}
	}

	if status == "error" || statusRaw == "error" || outcome == "error" {
		return EpisodeStatus{Label: "ERROR", Severity: "err", OutcomeKey: "error", Bucket: BucketError}
	}

	if outcome == "success_unverified" {
		return EpisodeStatus{Label: "UNVERIFIED", Severity: "muted", OutcomeKey: "success_unverified", Bucket: BucketUnverified}
	}

	if outcome == "success" {
		return EpisodeStatus{Label: "SUCCESS", Severity: "ok", OutcomeKey: "success", Bucket: BucketOK}
	}

	if outcome == "violated" {
		return EpisodeStatus{Label: "VIOLATED", Severity: "err", OutcomeKey: "violated", Bucket: BucketError}
	}

	return EpisodeStatus{Label: "UNKNOWN", Severity: "muted", OutcomeKey: "unknown", Bucket: BucketUnknown}
}

func shortEpisodeID(ep cli.EpisodeRow) string {
	if ep.EpisodeShort != "" {
		if strings.Contains(ep.EpisodeShort, "…") {
			return ep.EpisodeShort
		}
	}
	return shortenEpisodeID(ep.EpisodeID)
}

func derefString(value *string) string {
	if value == nil {
		return ""
	}
	return *value
}

func derefInt(value *int) int {
	if value == nil {
		return 0
	}
	return *value
}

func flagString(flags map[string]any, key string) string {
	if flags == nil {
		return ""
	}
	raw, ok := flags[key]
	if !ok {
		return ""
	}
	if value, ok := raw.(string); ok {
		return strings.ToLower(strings.TrimSpace(value))
	}
	return ""
}

func symbolForSeverity(severity string) string {
	switch severity {
	case "ok":
		return "●"
	case "warn":
		return "⚠"
	case "err":
		return "✗"
	default:
		return "○"
	}
}
