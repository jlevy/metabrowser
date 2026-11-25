---
type: is
id: is-01m89xq20v1f6sandg3zfk6ma8
title: "PR #841 A1: pin a new pull request's guide with git merge-base; the record's values for an existing or merged one"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/research/research-2026-11-22-annotated-collections-and-guided-pr.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m89xprnt4aby23f09h7bg3v9
hold: null
hold_until: null
created_at: 2026-11-25T17:58:04.058Z
updated_at: 2026-11-25T18:14:51.695Z
started_at: 2026-11-25T17:58:14.477Z
closed_at: 2026-11-25T18:14:51.692Z
close_reason: fixed in a6635aeb80e35d86c1190fa5a0af977e84144832; disposition reply https://github.com/jlevy/metabrowser/pull/841#issuecomment-7170643113
resolution: null
duplicate_of: null
---
Medium. skills/metabrowser/SKILL.md:632-637 and :668-670, changelog.d/mb-8ovf.md:1-4. Restore the common path: when opening the PR, fetch the base, pin merge_base with git merge-base origin/<base> HEAD and head with the pushed head, publish with gh pr create, then refresh and confirm the record's comparison equals the pins; take the record's values for an existing, merged, or closed PR. Review: https://github.com/jlevy/metabrowser/pull/841#pullrequestreview-6062463825
