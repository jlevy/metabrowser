---
type: is
id: is-01m6g1xqvvwtxcv49ahtf13bqf
title: "PR #285 C6: step 4's seam is stated as adds only children"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
hold: null
hold_until: null
created_at: 2026-11-03T06:35:40.271Z
updated_at: 2026-11-03T07:05:04.494Z
started_at: 2026-11-03T07:04:23.942Z
closed_at: 2026-11-03T07:05:04.493Z
close_reason: "fixed in b1dee9bf: the plan's step-4 bullet lists aria-owns, app.js's pane-wide listeners, the fallback, the row keys, the paint's reuse and placement, and the grid"
resolution: null
duplicate_of: null
---
Plan step-4 bullet (plan-2026-10-01-github-pulls-tab.md:635-639) and pulls-panel.js:11-15 say step 4 adds only a group; it also needs aria-owns, scoping app.js's #tree-pane listeners, the [data-tree-id] fallback, pulls-nav.js's row-key scope and walk, and the row grid. List these in the plan. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
