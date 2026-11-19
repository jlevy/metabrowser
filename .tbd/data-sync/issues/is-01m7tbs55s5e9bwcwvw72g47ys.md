---
type: is
id: is-01m7tbs55s5e9bwcwvw72g47ys
title: Chevron moves to the main page's foot, on the shortcut strip's row
kind: task
status: closed
priority: 2
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:56:01.976Z
updated_at: 2026-11-19T18:07:04.753Z
started_at: 2026-11-19T16:56:33.368Z
closed_at: 2026-11-19T18:07:04.751Z
close_reason: "PR #609 merged"
resolution: null
duplicate_of: null
---
Owner, 2026-11-19, verbatim: "move the < chevron to the bottom of the main panel but aligned to the right of the keyboard shortcut tips (T Quick Search etc) but same horizontal position". Supersedes mb-tl7p placement (top row); keeps its horizontal place in the gutter.

## Notes

PR #609. Chevron back on the shortcut strip's row (centered below its rule), horizontal place from #608 kept (gutter-centered, 24 px). nav-collapse.js anchor option + ResizeObserver set --nav-shortcut-row-top/-height on .container; .resize-handle::after stops above the row. Root token --nav-shortcut-row-height is the pre-measurement fallback and the hidden strip's min-height. view-header-chrome no longer places the chevron.
