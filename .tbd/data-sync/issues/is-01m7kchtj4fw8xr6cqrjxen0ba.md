---
type: is
id: is-01m7kchtj4fw8xr6cqrjxen0ba
title: "PR #453 A1: Phase 1 reader list misses pumpCores, noteListed, describePulls and the pulls-refresh route"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7f2vek3t6sca32adhd4gq33
hold: null
hold_until: null
created_at: 2026-11-16T23:54:49.283Z
updated_at: 2026-11-17T00:36:58.907Z
started_at: 2026-11-16T23:55:03.826Z
closed_at: 2026-11-17T00:36:58.906Z
close_reason: "fixed in a832c30 (PR #453); disposition reply https://github.com/jlevy/metabrowser/pull/453#issuecomment-6933923484"
resolution: null
duplicate_of: null
---
Review A (round 1) of PR #453, finding A1, severity Medium. Review: https://github.com/jlevy/metabrowser/pull/453#pullrequestreview-5916025215. Anchors: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md:1251-1255, :803-810; github/pulls-panel.js pumpCores, noteListed, describePulls; github/sidekick.py pulls-refresh; tests/golden/cli-github-pulls-refresh.txt. Fix: add the readers and the pulls-refresh route, golden and parity rows to the route table and Phase 1
