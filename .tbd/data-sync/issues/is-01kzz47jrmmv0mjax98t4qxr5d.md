---
type: is
id: is-01kzz47jrmmv0mjax98t4qxr5d
title: "PR #35 review R10: small cleanups in the keyboard modules"
kind: chore
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:43.604Z
updated_at: 2026-08-14T03:32:04.329Z
closed_at: 2026-08-14T03:32:04.329Z
close_reason: "Fixed in 78ee53e: dropped the duplicate href assignment, the void-discarded binding, and the redundant print selector."
---
keyboard_help.js sets projectLink.href twice; keyboard_shortcuts.js normalizeBinding binds keyDefinition only to void it; styles.css print block lists both .modal-overlay and the now-redundant .search-palette-overlay.
