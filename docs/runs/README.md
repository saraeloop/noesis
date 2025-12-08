# Episode Run Artifacts

Every episode writes immutable artifacts under `runs/<label>/<episode_id>/`. These files are append-only until `manifest.json` is sealed.

- `events.jsonl` — chronological cognitive events (observe/interpret/plan/act/reflect/learn) with lineage.
- `state.json` — structured episode state (goal, plan, actions, outcomes, links).
- `summary.json` — condensed episode summary and KPIs.
- `prompts.jsonl` — **experimental** prompt provenance (ADR-005/006, optional, behind `prompt_provenance_enabled`). Each line is a schema-tagged prompt record (`$schema_name: "prompt"`, `$schema_version: "1.1.0"`) with `episode_id`, `phase`, `agent_id`, `fingerprint`, `mode`, optional `event_id`, and:
  - `full` mode: includes `template`, `rendered`, `variables`, and `tags`.
  - `hash_only` mode: hashes only; omits bodies and variables.
  - `redacted` mode: stores placeholders for bodies/variables while keeping fingerprints and template identifiers.

When a run finishes, `manifest.json` captures integrity metadata for every artifact. Example (truncated SHA values):

```json
{
  "episode_id": "ep_01KARXTHS68GAYWGR2588QW2YJ",
  "schema_version": "manifest/1.0",
  "files": [
    { "kind": "events", "name": "events.jsonl", "sha256": "sha256:647d1f86...", "size_bytes": 7045 },
    { "kind": "state", "name": "state.json", "sha256": "sha256:a87f1e5e...", "size_bytes": 1637 },
    { "kind": "summary", "name": "summary.json", "sha256": "sha256:b5cf1cc8...", "size_bytes": 1265 },
    { "kind": "attachment", "name": "prompts.jsonl", "sha256": "sha256:a4099f6d...", "size_bytes": 537 }
  ]
}
```

Use `noesis artifacts verify <run_dir>` (or `noesis.artifacts.verify_manifest`) to re-hash files and detect tampering. Prompt provenance stays opt-in; turn it on via `prompt_provenance_enabled=true` and choose `prompt_provenance_mode` (`full` or `hash_only`).
