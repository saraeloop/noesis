// Package cli provides types and a client for interacting with the Noesis Python CLI.
package cli

// CliVersion represents the versioning block in all CLI JSON envelopes.
// Per ADR-011 and ADR-012, all --json output includes this block.
type CliVersion struct {
	SchemaVersion string `json:"schema_version"` // e.g., "cli/1.1"
	CompatMin     string `json:"compat_min"`     // e.g., "cli/1.0"
	CompatMax     string `json:"compat_max"`     // e.g., "cli/1.x"
}

// IsCompatible checks if a consumer version is within the [compat_min, compat_max] range.
// For simplicity, we just check if compat_max starts with "cli/1." for cli/1.x compatibility.
func (c CliVersion) IsCompatible(consumerVersion string) bool {
	// Simple check: if compat_max is "cli/1.x", any cli/1.* is compatible
	if c.CompatMax == "cli/1.x" && len(consumerVersion) >= 5 {
		return consumerVersion[:5] == "cli/1"
	}
	return c.SchemaVersion == consumerVersion
}
