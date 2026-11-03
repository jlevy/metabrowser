---
type: is
id: is-01m6g1xqvvwtxcv49ahtf13bqf
title: "PR #285 C6: step 4's seam is stated as adds only children"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
created_at: 2026-11-03T06:35:40.271Z
updated_at: 2026-11-03T06:35:40.271Z
---
Plan step-4 bullet (plan-2026-10-01-github-pulls-tab.md:635-639) and pulls-panel.js:11-15 say step 4 adds only a group; it also needs aria-owns, scoping app.js's #tree-pane listeners, the [data-tree-id] fallback, pulls-nav.js's row-key scope and walk, and the row grid. List these in the plan. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
