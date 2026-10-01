---
type: is
id: is-01m3w2g9nnayhe0h4rqp1k39ma
title: "Final landing docs for the v0.12 stack: QA playbook refresh, review ledger, landing status"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T15:49:36.040Z
updated_at: 2026-10-01T17:12:42.986Z
started_at: 2026-10-01T15:51:06.955Z
---
The docs at the stack tip predate the last ten PRs (#251-#258, #254). Refresh docs/qa-v012-repository-library.md (stale Phase 1 intro, Phase 3 title, Phase 7 table, 'stack #218' naming; missing: checks only the user can make, a browser pass over standard features on a plain folder, URL-like folder names, the test tiers, --doctor) with a short walk-through section; refresh the landing status in the alpha-testing plan and the follow-ups table in the thin-mirror plan; add the per-layer review ledger the landing checklist asks for (last one is the #216 comment of 2026-09-22); record the tip's verification (full local gate, golden-update no-op, CPU-time pairs).

## Notes

2026-10-01: draft PR #260 (codex/v012-landing-docs, base codex/v012-tests-git-pin at 373b59a9). Runbook refreshed with the walk-through, Phase 0 doctor and plugin steps, Phase 1 tiers/golden no-op/startup budget/test-report, Phase 3 folder steps with a browser pass; review ledger added (39 rows plus #247); landing status rewritten; thin-mirror follow-ups through #260; QA record addendum. Every added or changed runbook command was run on the tip except make test-live-github and the live-GitHub parts of the walk-through. Found and filed mb-tdmd (connection wait after about five full page loads in a tab). The #244 ledger row is 'in review' and waits for the coordinator. A sibling draft, #259, is on the same base, so the chain is forked at the tip until one is restacked. Not closed: the coordinator owns closing.
