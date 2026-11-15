---
type: is
id: is-01m7g6dbyvtsbm7pzrgvmqreh4
title: Nav tab toolbars wrap when narrow, one design-system rule with a set line height
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:09:48.506Z
updated_at: 2026-11-15T18:13:53.639Z
started_at: 2026-11-15T18:13:53.638Z
---
Found while doing mb-x1h6 (#445, 6ef17dbe, 2026-11-15).

With Show ignored on the Files filter row, the row fits the default 299 px pane in the default font set (1.89 px to spare at its widest: "No grouping", a filter set so Clear and the badge show), after a spacing-only fix to the chevron's badge. It still overflows elsewhere, measured in headless Chrome:
- The system font set's wider face (SF on macOS): about 18 px over at "No grouping" and about 13 px at "By file type", at 299 px.
- Narrower panes (the pane drags down to 180 px): over below about 297 px with a filter set, and below about 245 px with none. At 180 px the chevron's right edge is at 233 px, so the pane clips the chevron entirely and cuts Show ignored, even with no filter set. Before mb-x1h6 the row fit at 180 px.

Options (decision pending with the user):
- Let the row wrap at its natural break: Clear and the chevron drop to a second line, right-aligned, only when there is no room. Nothing is cut or truncated.
- Let the Group by trigger truncate with an ellipsis.
- Make the row scroll along its one line, as `.nav-toolbar` does on the other tabs.
- Shorter labels, or Show ignored back in the drawer below some width.

Done when the row shows every control whole, or by a documented rule, at every pane width from 180 px and in both font sets, measured in Chrome and pinned in tests/test_files_tab_chrome.py.

## Notes

Decision, the user (2026-11-15), verbatim: "on narrow screens wrap when narrow on the tabs" and "make sure line height on tabs is appropriate too. This should be a consistent design system that works everywhere. Tabs containers become too narrow."

Scope widened from the Files row to every nav tab: one shared rule for the nav pane's tab toolbars (the Files filter row with Group by and Show ignored, the Pulls toolbar, the Commits toolbar) and the nav tab bar itself if it overflows. Each wraps at its natural break when the pane is too narrow, so no control is clipped or truncated, with a line height and row gap from tokens that read as one toolbar. Measured in Chrome from the 180 px minimum pane up to the default 299 px and wider, in both font sets; pinned in the Files, Pulls and Commits Chrome tests; stated once in docs/design-system.md. Delivered as its own PR at the top of stack #446.
