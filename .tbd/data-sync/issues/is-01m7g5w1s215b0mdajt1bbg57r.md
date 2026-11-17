---
type: is
id: is-01m7g5w1s215b0mdajt1bbg57r
title: "PR page: the branches get their own line under the author's sentence"
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:00:21.025Z
updated_at: 2026-11-17T05:58:42.974Z
started_at: 2026-11-15T18:00:52.876Z
---
The user's request (2026-11-15), verbatim:

"and the branches should be on their own line, below the "jlevy wants to merge" line"

Done when the head and base branch names leave the author's sentence ("jlevy wants to merge N commits") for a line of their own directly below it, keep their links, copy and truncation behavior, the header's box stays fixed across states (every row present at one line from first paint), and the design system, the header golden or session if one pins the sentence, and the header Chrome checks say so.

## Notes

2026-11-15: done in commit 29f7d846d on claude/pull-timeline (PR #451), pushed. The branches have their own line (.github-pull-branches, min-height 1lh) under the author's sentence, which now ends at the commit count. The header keeps one box: rows match the empty record at every width in the header Chrome checks. Pins updated: the mount session, test_reserved_chrome, the avatar-repaint build count (42 -> 43), the design system, the plan and the CHANGELOG. The github-pull-page-session golden summary line is a model summary, so it is unchanged.
