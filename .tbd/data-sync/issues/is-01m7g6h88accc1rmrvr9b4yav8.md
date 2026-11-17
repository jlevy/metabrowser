---
type: is
id: is-01m7g6h88accc1rmrvr9b4yav8
title: "Stack keys: Next and Previous in stack move to Ctrl+N and Ctrl+P"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T18:11:55.785Z
updated_at: 2026-11-17T05:58:50.404Z
started_at: 2026-11-15T18:13:53.391Z
closed_at: 2026-11-16T16:30:53.121Z
close_reason: "Merged into main at afda3599f (stack #446 lower layers)."
resolution: null
duplicate_of: null
---
The user's request (2026-11-15), verbatim:

"change the keys for prev and next from shift-P and shift-N to ctrl-P and ctrl-N so we free up P and N"

Today `static/pulls-nav.js` `registerKeys` binds N ("Next in stack", `pulls.stack.top`) and P ("Previous in stack") as plain global keys, and Shift is ignored, so they show as N and P. `static/keyboard-shortcuts.js` never matches a key with Ctrl, Alt, or Meta held (`DISQUALIFYING_MODIFIERS`: "the chords belong to the browser and the platform"), so a Ctrl binding needs the registry to accept a declared Control modifier on purpose.

Done when:
- Next and Previous in stack are Ctrl+N and Ctrl+P, and plain N and P no longer do anything there.
- The registry accepts a binding that declares Control. Such a binding matches only Control with no Alt or Meta, so AltGr (Ctrl+Alt) still types its character. It is not taken from a text field, where macOS uses Control+N and Control+P to move the caret. Help and the Shift reveal show it as the platform writes it (⌃N on macOS, Ctrl+N elsewhere).
- docs/design-system.md and the keyboard docs state the rule for Control chords: which are allowed and why. The keymap goldens, sessions and Help copy are updated.
- The platform limit is stated: Chrome on Windows and Linux keeps Ctrl+N for a new window and pages cannot take it, while macOS (the app and its browsers) leaves Control+N and Control+P free.
