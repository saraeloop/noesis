# Feature Request: Refactor incident triage demos onto LangGraph + human approvals

## Overview
Elevate the sandbox demos under `examples/incident_triage/` into realistic reference flows that exercise Noēsis reasoning loops.

## Motivation
- Replace heuristic keyword checks with actual observability and CI/CD context so the demo reflects production workflows.
- Demonstrate LangGraph/LangChain integration in a way contributors can extend.
- Showcase human-in-the-loop approval adapters instead of deterministic rules.

## Proposed Implementation
- Prototype entry point: wrap the LangGraph pipeline in `incident_graph`.
- Required datasets/assets: mocked observability payloads, deploy diffs, approval transcripts.
- Migration considerations: keep deterministic mode behind a flag for tutorials.

## Related Components
- [x] Runtime / Faculties
- [x] CLI / Viewer
- [x] Schema / Config
- [x] Learning / Insight
- [x] Infrastructure / CI
- [x] Evaluation / Benchmarks
- [x] Safety / Alignment guardrails

## Success Criteria & Measurement
- Benchmarks: incident replay suite passes with LangGraph-enabled pipeline.
- Baseline: current deterministic heuristics.
- Telemetry: viewer timeline shows reasoning + approval events with artifacts attached.

## Safety & Risk
- Ensure new integrations degrade gracefully when external services are unavailable.
- Document access patterns for observability secrets; provide mocks by default.

## Artifacts & Research Assets
- Dataset snapshot or subset (redacted incident payloads).
- Schema fingerprint and config diff for new adapters.
- LangGraph workflow config + minimal repro script.
- Checkpointed approval policy (if any) and evaluation notebooks.

## Additional Context
- Mirrors TODOs in `examples/incident_triage/app_incident_triage.py` and `examples/incident_triage/gradio_app.py`.
- Unlocks richer documentation and live demos.
