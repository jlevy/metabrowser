---
type: is
id: is-01m7tbs4pg3p984ty3ndmjttk5
title: Main page's focus ring is covered by a pull request's tab bar
kind: bug
status: closed
priority: 2
version: 5
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T16:56:01.486Z
updated_at: 2026-11-20T17:00:12.105Z
started_at: 2026-11-19T16:56:32.898Z
closed_at: 2026-11-19T18:07:02.880Z
close_reason: "PR #609 merged"
resolution: null
duplicate_of: null
---
Owner, 2026-11-19, verbatim: "the border on the main window that indicates focus seems to have a lower z index than some backgrounds, the part of the tabs with the Conversation and Changs section is covering up the blue border indicating focus". Cause: .preview-pane:focus-visible draws an inset outline on the scroller, which paints under its scrolled content.

## Notes

PR #609 (branch claude/focus-ring-chevron). Ring moved from .preview-pane:focus-visible outline to .preview-frame:has(> .preview-pane:focus-visible)::after (2px border, pointer-events none, z --z-overlay). nav-collapse-chrome samples a screenshot pixel at the frame's top edge over an absolutely positioned red band: old outline painted white/red (covered), new ring paints --link.
