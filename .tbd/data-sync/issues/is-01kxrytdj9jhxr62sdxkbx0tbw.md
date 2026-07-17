---
type: is
id: is-01kxrytdj9jhxr62sdxkbx0tbw
title: Bound default tree expansion to one-page budget
kind: bug
status: in_progress
priority: 2
version: 2
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:13:19.176Z
updated_at: 2026-07-17T21:13:27.711Z
---
Initial tree rendering currently auto-expands every eligible top-level folder, so large directories such as tests flood the navigation pane. Use a deterministic visible-row budget of roughly one page: expand compact/easy folders only while their immediate contents fit the remaining budget, otherwise leave them collapsed. Preserve explicit expansion state and special-directory behavior where it fits the same budget.
