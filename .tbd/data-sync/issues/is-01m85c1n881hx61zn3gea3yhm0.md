---
type: is
id: is-01m85c1n881hx61zn3gea3yhm0
title: "PR #765 A4: an emptied Markdown file draws a blank body in Rendered Current"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:19.333Z
updated_at: 2026-11-23T23:35:08.329Z
started_at: 2026-11-23T23:35:08.327Z
---
Low. diff-markdown.js:625-630 (applyShow hides every removed block), :613-619. Source Current says 'This file is empty now.' (currentAbsence, diff-view.js:736-744); Rendered Current should say the same.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
