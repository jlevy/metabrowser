---
type: is
id: is-01m8bbh9wvgrpaatn3b8xyz73b
title: "Menus: end the press window on pointercancel/contextmenu/no-click, document rule 2, unnest the File type holder"
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T07:18:50.010Z
updated_at: 2026-11-26T08:20:29.232Z
started_at: 2026-11-26T08:20:29.231Z
---
Review A of #873 Lows: A1 a press with no click (disabled row) leaves the press window open until the next press/click/key, so a scripted outside focus is swallowed; end it at pointercancel, contextmenu, and after a mouse pointerup with no click, with a session case. A2 document in design-system.md, plugins.md and types.d.ts that opened() leaves a menu another handle holds open by the same trigger. A3 the Markdown layer's nested bind makes a holder whose inside is the whole container (filter-controls.js:1063); remove the nesting so rule 2 is not needed. Also rename onEscape, which now acts on every key.
