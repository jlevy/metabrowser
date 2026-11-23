---
type: is
id: is-01m82h15ejqn4675xxm6c4xaz8
title: "Phase 1 (b): conditional account check, so probes and jobs spend no core call on the sign-in"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-22T21:01:42.735Z
updated_at: 2026-11-23T01:43:52.073Z
started_at: 2026-11-23T01:43:52.072Z
---
Replace gh auth status (1 core call) in gh_lists.active_account with a conditional gh api user carrying the last ETag, which GitHub answers 304 for free; keep gh_status's rich check for setup guidance; update the fake gh and goldens. See the plan's Phase 1.
