# Migration Notes

## v0.9.5 – Governance & Direction Hardening

- **Directive payloads** now emit a deterministic `directive_id` while continuing to write the legacy `legacy_directive_id` UUID. Consumers should switch to `directive_id` and treat the legacy field as backward compatibility only.
- **Governance payloads** add `governance_id` alongside the existing `decision_id`. Downstream systems must persist the new stable identifier for lineage and deduplicate via the legacy field during the transition.
- Schema versions for `direction` and `governance` increased; bump your registry entries and regenerate fixtures as part of upgrades.

