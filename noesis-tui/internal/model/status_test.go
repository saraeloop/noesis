package model

import (
	"testing"

	"noesis.dev/tui/internal/cli"
)

func strPtr(value string) *string {
	return &value
}

func boolPtr(value bool) *bool {
	return &value
}

func intPtr(value int) *int {
	return &value
}

func TestClassifyEpisode(t *testing.T) {
	cases := []struct {
		name  string
		ep    cli.EpisodeRow
		want  EpisodeBucket
		label string
		sev   string
	}{
		{
			name:  "vetoed",
			ep:    cli.EpisodeRow{Status: "vetoed"},
			want:  BucketBlocked,
			label: "VETOED",
			sev:   "warn",
		},
		{
			name:  "error",
			ep:    cli.EpisodeRow{Status: "error", Outcome: strPtr("error")},
			want:  BucketError,
			label: "ERROR",
			sev:   "err",
		},
		{
			name: "audit",
			ep: cli.EpisodeRow{
				Outcome: strPtr("success"),
				Flags:   map[string]any{"governance_mode": "audit"},
			},
			want:  BucketAudit,
			label: "AUDIT",
			sev:   "warn",
		},
		{
			name:  "verify failed",
			ep:    cli.EpisodeRow{Outcome: strPtr("goal_not_achieved")},
			want:  BucketVerifyFailed,
			label: "VERIFY FAILED",
			sev:   "err",
		},
		{
			name:  "unverified",
			ep:    cli.EpisodeRow{Outcome: strPtr("success_unverified"), Success: boolPtr(false)},
			want:  BucketUnverified,
			label: "UNVERIFIED",
			sev:   "muted",
		},
		{
			name: "vetoed via veto_count",
			ep: cli.EpisodeRow{
				VetoCount: intPtr(1),
				Flags:     map[string]any{"governance_mode": "enforce"},
			},
			want:  BucketBlocked,
			label: "VETOED",
			sev:   "warn",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := classifyEpisode(tc.ep)
			if got.Bucket != tc.want {
				t.Fatalf("bucket: got %s want %s", got.Bucket, tc.want)
			}
			if got.Label != tc.label {
				t.Fatalf("label: got %s want %s", got.Label, tc.label)
			}
			if got.Severity != tc.sev {
				t.Fatalf("severity: got %s want %s", got.Severity, tc.sev)
			}
		})
	}
}
