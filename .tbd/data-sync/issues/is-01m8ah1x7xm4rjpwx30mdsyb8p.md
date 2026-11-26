---
type: is
id: is-01m8ah1x7xm4rjpwx30mdsyb8p
title: Nav Refresh becomes a circular-arrow icon left of the gear
kind: task
status: closed
priority: 1
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T23:36:02.556Z
updated_at: 2026-11-26T03:09:02.361Z
started_at: 2026-11-25T23:37:05.600Z
closed_at: 2026-11-26T03:09:02.359Z
close_reason: "Merged in #858"
resolution: null
duplicate_of: null
---
User request 2026-11-25: the Refresh button moves to a refresh icon (circular arrow or similar) at the top of the nav column, just left of the gear icon.

## Notes

User decisions 2026-11-25: (1) Refresh is global: the icon shows and works on every nav tab (Files, Commits, Pulls), unless there is a good reason not to. (2) A press refreshes everything, visible parts first (open main view and the tab in front), then hidden tabs. Glyph drawn by the server from first paint.
