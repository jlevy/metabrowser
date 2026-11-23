---
type: is
id: is-01m85c186mdfrmndf5n8y91j2q
title: "PR #765 A1: the stack #759, #766, #765 was not a formal GitHub stack"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:05.936Z
updated_at: 2026-11-23T23:34:56.129Z
started_at: 2026-11-23T23:34:56.126Z
---
High (process). gh api repos/jlevy/metabrowser/stacks?pull_request=N returned [] for 759, 766 and 765. Fix: gh stack link the three in order. The coordinator links the native stack.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
