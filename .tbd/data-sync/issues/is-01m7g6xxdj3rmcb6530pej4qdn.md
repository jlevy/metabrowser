---
type: is
id: is-01m7g6xxdj3rmcb6530pej4qdn
title: "Group by menu: A chooses By age and T chooses By file type"
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
created_at: 2026-11-15T18:18:50.673Z
updated_at: 2026-11-15T18:20:08.005Z
started_at: 2026-11-15T18:20:08.004Z
---
The user's request (2026-11-15), verbatim:

"also a keyboard change, the menu like "By grouping" should assign keys to the By age and By file type (perhaps A and T?)"

Done when, with the Group by menu open, A chooses By age and T chooses By file type, and the menu shows each row's key the way the app shows keys elsewhere (the Shift reveal and Help). No grouping gets a key too if the convention calls for one. The keys work only while that menu is open and never steal a key a text field or a global shortcut needs. The menu-key convention is stated once in docs/design-system.md, so other menus can follow it. A browserless session covers the key handling, as AGENTS.md's parity rules require, with a Chrome check for anything browser-only.
