---
type: is
id: is-01m7jh00g9ek0gw3ym2g5wgptr
title: "Diff summary reads '19 files changed · 10 A, 5 D, 4 M · +1,234 −567': bold numbers, status-colored letters, muted punctuation, as one design-system rule"
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:53:13.991Z
updated_at: 2026-11-16T21:04:55.788Z
closed_at: 2026-11-16T21:04:55.787Z
close_reason: "Merged in #479 (7da81ab57)"
resolution: null
duplicate_of: null
---
Owner, 2026-11-16: "also one more thing, the diff summary shows this format: 19 changed files (10 added, 5 removed, 4 modified)  +1234 -567 let's change this to be more intuitive 19 files changed 10 A, 5 D, 4 M +1234 -567 where the 10 A and 5 D and 4 M are the appropriate colors for A D and M we already have in diff views"

## Notes

Owner revisions, 2026-11-16: "or better 19 files changed · 10 A 5 D 4 M · +1234 -567", then "or actually 19 files changed · 10 A, 5 D, 4 M · +1234 -567 is best, where punctuation is gray. Let's make this the consistent design system." Final wording sent to the layer-28 agent (claude/diff-summary-letters): one shared muted-punctuation primitive applied across count summaries.
