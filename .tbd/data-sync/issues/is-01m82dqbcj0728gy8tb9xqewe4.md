---
type: is
id: is-01m82dqbcj0728gy8tb9xqewe4
title: Open pull request page shows GitHub changes within seconds, not up to 90 s
kind: feature
status: in_progress
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/709
    at: 2026-11-22T22:59:18.601Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-22T20:03:55.409Z
updated_at: 2026-11-22T22:59:21.858Z
started_at: 2026-11-22T20:04:03.347Z
---
A merge on github.com took 48 s to show on an open, visible pull request page (fdu #214, 2026-11-22: merged 19:29:37, shown 19:30:25). The page polls the server every SLOW_POLL_MS (30 s) and the server treats a record as fresh for FRESHNESS_WINDOW_S (60 s), so a change can take up to ~90 s. Goal: while a pull request page is visible, check GitHub for that pull request every few seconds with a cheap conditional request, refresh the record when it changed, and show it at once.

## Notes

Design for review: PR jlevy/metabrowser#696 (draft, docs only). The owner answered the plan's open questions on 2026-11-22: ATTENDED_PROBE_S 5 s and a 600/h self-ceiling; no live-test draft PR was approved, so nothing is published to GitHub for testing.

This bead is Phase 1 (a), the probes, under epic mb-dip2 (on Linear). Phase 1 (b), the conditional account check, is mb-1bir; Phase 2 is mb-lcwy. Implemented on branch claude/pull-probe-phase1, stacked on #696.

2026-11-22: PR jlevy/metabrowser#709 (stack #710 on #696) carries the probes, the page cadence, docs, and goldens. Local: lint, types, parity, changelog, and 144 focused tests pass; the full golden check timed out tryscript setup hooks under a load average near 300, so CI is the full gate.
