---
type: is
id: is-01m85c29empds45q6httf9shqy
title: "PR #765 A9: patchRowCounts reserves no row for a held file that is deleted or emptied in Current"
kind: bug
status: closed
priority: 4
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m8577bzvw6qnfffw9g5f56x2
hold: null
hold_until: null
created_at: 2026-11-23T23:32:40.012Z
updated_at: 2026-11-24T01:06:02.571Z
started_at: 2026-11-23T23:35:25.887Z
closed_at: 2026-11-24T01:06:02.565Z
close_reason: "Fixed in 462859300: patchRowCounts counts a held deleted or emptied file in Current as one notice row; diff-view-behavior.js check."
resolution: null
duplicate_of: null
---
Suggestion. diff-view.js:2655-2683: count one notice row where currentAbsence applies.

Review A on PR #765: https://github.com/jlevy/metabrowser/pull/765#pullrequestreview-6031120972
