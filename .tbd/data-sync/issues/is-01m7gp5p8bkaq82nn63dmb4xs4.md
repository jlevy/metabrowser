---
type: is
id: is-01m7gp5p8bkaq82nn63dmb4xs4
title: "Consistency fixes: code (mb-r5jr review A1-A10, B4, C2, C4, C6, C8, C9)"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7g5yrx2z5bck8g4p1y4g6rx
hold: null
hold_until: null
created_at: 2026-11-15T22:45:14.111Z
updated_at: 2026-11-16T20:03:32.483Z
started_at: 2026-11-15T22:46:17.289Z
closed_at: 2026-11-16T20:03:32.483Z
close_reason: "Merged into main at 1dcbe93 (stack #446 #464-#478) after the gate and the whole-stack review."
resolution: null
duplicate_of: null
---
Code fixes from the mb-r5jr design-system consistency review (2026-11-15), as one pull request at the top of stack #446: A1-A7, A9, A10, B4, and the coordinator's decisions C2, C4, C6, C8, C9. The full findings and decisions are in the coordinator's attic/coord/reviews/mb-r5jr-findings.md; the user's request was "Let's make all of these consistent design system changes too, so everything is following standard conventions."

Done when each listed finding is fixed as its Fix says, measured in Chrome where it is paint, with tests that would fail on the old code, and the design-system lines for these code changes updated.
