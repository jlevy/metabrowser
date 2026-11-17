---
type: is
id: is-01m7gp5ppkv5m3ecb607b1r71r
title: "Consistency fixes: docs and CHANGELOG (mb-r5jr review B1-B8, A8, C1, C3, C7)"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7g5yrx2z5bck8g4p1y4g6rx
hold: null
hold_until: null
created_at: 2026-11-15T22:45:14.578Z
updated_at: 2026-11-17T05:59:15.475Z
started_at: 2026-11-15T22:46:12.401Z
closed_at: 2026-11-16T20:03:32.862Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
Docs fixes from the mb-r5jr design-system consistency review (2026-11-15), as one pull request on top of the code-fix pull request: B1 (the CHANGELOG Unreleased block reads as one change from 0.12.0), B2, B3, B5-B8, A8, and the coordinator's decisions C1 and C7 and the C3 sentence. The full findings and decisions are in the coordinator's attic/coord/reviews/mb-r5jr-findings.md.

Done when each listed item is fixed, the CHANGELOG has no entry contradicting another, and make format and lint-check pass.
