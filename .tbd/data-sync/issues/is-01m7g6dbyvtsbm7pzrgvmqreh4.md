---
type: is
id: is-01m7g6dbyvtsbm7pzrgvmqreh4
title: "Files filter row: fit narrow panes and the system font set with Show ignored on it"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T18:09:48.506Z
updated_at: 2026-11-15T18:09:48.506Z
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
