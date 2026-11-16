---
type: is
id: is-01m7k4ksss6yjk82nvrjkx2d39
title: "PR #484 A8: a listing past the Git read cap is unavailable, not too_large, and is not kept"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jwtbafwhwvmsjwvzvz9xg9
hold: null
hold_until: null
created_at: 2026-11-16T21:36:05.432Z
updated_at: 2026-11-16T21:36:15.996Z
started_at: 2026-11-16T21:36:15.993Z
---
Low. pull_stack_change.py:264-265 maps GitOutputTooLargeError to unavailable. Review A (round 1) of PR #484: https://github.com/jlevy/metabrowser/pull/484#pullrequestreview-5928039724
