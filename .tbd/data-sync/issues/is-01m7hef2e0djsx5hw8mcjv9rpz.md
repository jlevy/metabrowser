---
type: is
id: is-01m7hef2e0djsx5hw8mcjv9rpz
title: "PR #459 A1: Shift badges a lower-layer control on a letter an open menu holds"
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
created_at: 2026-11-16T05:49:47.327Z
updated_at: 2026-11-16T05:51:13.349Z
started_at: 2026-11-16T05:49:54.819Z
closed_at: 2026-11-16T05:51:13.348Z
close_reason: "Fixed in 20456e846: badges use reachableBindings, as the strip does; confirmed by the new block in tests/dom/keyboard-shortcuts-behavior.js (fails before the fix)."
resolution: null
duplicate_of: null
---
Low. src/metabrowser/static/keyboard-shortcuts.js:877-891 (reconcileBadges) badged each ready command's first live target with bindings[0], while snapshot (:1487-1500) drops a binding a live command in a higher layer holds. A view tab on A or N stayed badged while Group by's A or N was live. PR #459, review A: https://github.com/jlevy/metabrowser/pull/459#pullrequestreview-5915454708
