---
type: is
id: is-01m7hef3qewfax0cfv4m3apq2d
title: "PR #459 A3: docs/plugins.md omits filterControls.bind's focus behavior and the new exports"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjfyhee19b9jnbk7nvqfk
hold: null
hold_until: null
created_at: 2026-11-16T05:49:48.652Z
updated_at: 2026-11-16T05:51:14.864Z
started_at: 2026-11-16T05:49:55.757Z
closed_at: 2026-11-16T05:51:14.863Z
close_reason: "Fixed in 5d1999712: docs/plugins.md describes bind's focus, focusMenu, keepFocus, activateMenuRow, and key/anyKey scope."
resolution: null
duplicate_of: null
---
Low. docs/plugins.md:540-541 and :563-566 do not describe bind's focus moves, the Escape guard, focusMenu, keepFocus, activateMenuRow, or the key and anyKey options (types.d.ts:887-971). PR #459, review A: https://github.com/jlevy/metabrowser/pull/459#pullrequestreview-5915454708
