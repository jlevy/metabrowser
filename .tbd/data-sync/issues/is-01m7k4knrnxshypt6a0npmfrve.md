---
type: is
id: is-01m7k4knrnxshypt6a0npmfrve
title: "PR #484 A1: stack line counts the base branch's own changes when the bottom's record is older"
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7jwtbafwhwvmsjwvzvz9xg9
hold: null
hold_until: null
created_at: 2026-11-16T21:36:01.301Z
updated_at: 2026-11-16T23:41:07.953Z
started_at: 2026-11-16T21:36:11.610Z
---
High. pull_stack_change.py:189-198 takes the left end from the bottom's cached record.comparison.base; :211-216 compares it with the top's head; golden tests/golden/cli-github-stack-change.txt:175-179 pins the overcount. Review A (round 1) of PR #484: https://github.com/jlevy/metabrowser/pull/484#pullrequestreview-5928039724

## Notes

2026-11-16, owner's decision (relayed by the coordinator from chat), asked what a merged stack's heading should show: first "Historical change", then: "A stack should simply be an accumulation of PRs, so it makes no sense to hide the diff. The stack historically is the set of PRs it consists of."

Escalated because the base-branch left end (fa7c746) gave 18 of this repository's 19 stacks, all merged by merge commit, an empty change ("+0 −0").

Fixed in 95a01b7 (on head 4cac85d): a stack's change is its members' own cached lists of changed files accumulated bottom first, by pull_change_sums.accumulate (every file once, followed across renames, composed status, lines summed). No Git, no GitHub, no fetch. The base-branch left end and no_base_branch are reverted. Golden: stack #70 = #8 + #10, 1 A, 1 M, +3 −0.
