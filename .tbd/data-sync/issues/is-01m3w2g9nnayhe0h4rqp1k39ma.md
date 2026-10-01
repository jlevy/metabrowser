---
type: is
id: is-01m3w2g9nnayhe0h4rqp1k39ma
title: "Final landing docs for the v0.12 stack: QA playbook refresh, review ledger, landing status"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T15:49:36.040Z
updated_at: 2026-10-01T15:51:06.958Z
started_at: 2026-10-01T15:51:06.955Z
---
The docs at the stack tip predate the last ten PRs (#251-#258, #254). Refresh docs/qa-v012-repository-library.md (stale Phase 1 intro, Phase 3 title, Phase 7 table, 'stack #218' naming; missing: checks only the user can make, a browser pass over standard features on a plain folder, URL-like folder names, the test tiers, --doctor) with a short walk-through section; refresh the landing status in the alpha-testing plan and the follow-ups table in the thin-mirror plan; add the per-layer review ledger the landing checklist asks for (last one is the #216 comment of 2026-09-22); record the tip's verification (full local gate, golden-update no-op, CPU-time pairs).
