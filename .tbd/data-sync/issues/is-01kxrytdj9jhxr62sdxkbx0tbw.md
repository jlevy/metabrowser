---
type: is
id: is-01kxrytdj9jhxr62sdxkbx0tbw
title: Bound default tree expansion to one-page budget
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:13:19.176Z
updated_at: 2026-07-17T21:29:08.447Z
closed_at: 2026-07-17T21:29:08.447Z
close_reason: Implemented and verified the compact tab spacing, reduced embedded-document top spacing, shared toggle/tab label typography, larger Markdown prose, and viewport-bounded default tree expansion; refreshed the README screenshot and passed make verify with 709 tests.
---
Initial tree rendering currently auto-expands every eligible top-level folder, so large directories such as tests flood the navigation pane. Use a deterministic visible-row budget of roughly one page: expand compact/easy folders only while their immediate contents fit the remaining budget, otherwise leave them collapsed. Preserve explicit expansion state and special-directory behavior where it fits the same budget.
