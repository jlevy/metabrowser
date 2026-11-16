---
type: is
id: is-01m7k4knrnxshypt6a0npmfrve
title: "PR #484 A1: stack line counts the base branch's own changes when the bottom's record is older"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jwtbafwhwvmsjwvzvz9xg9
hold: null
hold_until: null
created_at: 2026-11-16T21:36:01.301Z
updated_at: 2026-11-16T21:36:11.612Z
started_at: 2026-11-16T21:36:11.610Z
---
High. pull_stack_change.py:189-198 takes the left end from the bottom's cached record.comparison.base; :211-216 compares it with the top's head; golden tests/golden/cli-github-stack-change.txt:175-179 pins the overcount. Review A (round 1) of PR #484: https://github.com/jlevy/metabrowser/pull/484#pullrequestreview-5928039724
