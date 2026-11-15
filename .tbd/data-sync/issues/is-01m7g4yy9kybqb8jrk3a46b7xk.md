---
type: is
id: is-01m7g4yy9kybqb8jrk3a46b7xk
title: "Files tab: Show ignored sits beside Group by on the filter row"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T17:44:27.186Z
updated_at: 2026-11-15T17:45:10.439Z
started_at: 2026-11-15T17:45:10.438Z
---
The user's request (2026-11-15), verbatim:

"On the Files tab, let's move the "Show ignored" checkbox to next to the group dropdown (above the toggle)"

Follow-up to mb-sogv (#445), which put Show ignored in the chevron drawer with the three filters.

Done when:
- Show ignored is on the always-visible Files filter row, right after the Group by menu, and out of the drawer; a Git revision still omits it.
- The chevron's badge counts only the drawer's filters (Modified within, File type, Minimum file size), since the row shows Show ignored's own state; Clear still resets every filter, Show ignored included, and keeps the grouping.
- The row fits the default 299 px pane without overflow in its widest state (Group by at its longest value, a filter set so Clear and the badge show), measured in Chrome and recorded beside the rule.
- docs/design-system.md "Grouping the Files Tree", CHANGELOG, the plan spec, the Files Chrome test, and the Group by session golden say so.
