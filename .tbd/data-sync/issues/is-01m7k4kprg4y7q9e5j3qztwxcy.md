---
type: is
id: is-01m7k4kprg4y7q9e5j3qztwxcy
title: "PR #484 A3: a failed re-read drops a line the keep still holds"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jwtbafwhwvmsjwvzvz9xg9
hold: null
hold_until: null
created_at: 2026-11-16T21:36:02.319Z
updated_at: 2026-11-16T23:56:09.225Z
started_at: 2026-11-16T21:36:12.531Z
closed_at: 2026-11-16T23:56:09.224Z
close_reason: "fixed on PR #484 at fea8e7f; disposition reply https://github.com/jlevy/metabrowser/pull/484#issuecomment-6933084573"
resolution: null
duplicate_of: null
---
Medium. stack-lines.js:284-286 and :305-316 write key null over the outcome; :212-218 kept(); contract at :327-330. Review A (round 1) of PR #484: https://github.com/jlevy/metabrowser/pull/484#pullrequestreview-5928039724
