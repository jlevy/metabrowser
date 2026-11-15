---
type: is
id: is-01m7g7k4yj24780pbdw21skwgh
title: "PR page title: icon and title start left, the number right-aligned above the stack chip"
kind: bug
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
created_at: 2026-11-15T18:30:26.513Z
updated_at: 2026-11-15T18:30:45.367Z
started_at: 2026-11-15T18:30:45.366Z
---
Found while doing mb-cf0l (#451, 5efb99b7, 2026-11-15). The user described "the right aligned PR number" when placing the stack chip: "put it right aligned below the right aligned PR number, on same line as author".

The PR page title is a three-column grid: state icon, text (`minmax(0, max-content)`), number. The outer columns share any spare width, and the number starts right after the title. So the number reaches the header's content edge only when the title fills its line. A short title sits centred: at 980 px, "Count to two in the app" spans 361 to 608 px, the icon sits alone at 24 to 48 px, and "#7" starts at 616 px. Same at 560 px.

Done when the icon and the title start at the header's left edge, and the number is right-aligned at the content edge for every title length, so it stands directly above the stack chip that ends the author's row. A title of two lines still keeps its number, with the clamp and tooltip unchanged. Measured in Chrome at 980, 560, 360 and 320 px for short and long titles, pinned in the header Chrome checks, and stated in the design system's PR page layout.
