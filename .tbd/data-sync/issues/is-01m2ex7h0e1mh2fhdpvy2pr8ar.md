---
type: is
id: is-01m2ex7h0e1mh2fhdpvy2pr8ar
title: Tree movement keys are inert after a row is clicked before the keyboard layer attaches
kind: bug
status: closed
priority: 2
version: 2
labels:
  - keyboard
  - navigation
dependencies: []
created_at: 2026-09-14T02:51:36.331Z
updated_at: 2026-09-14T03:10:21.079Z
closed_at: 2026-09-14T03:10:21.077Z
close_reason: "Fixed in stacked PR on claude/tree-focus-before-attach (commit 3963465a, base claude/jk-list-navigation / PR #111): the first anchor repair adopts an already-focused row and activates the tree scope whenever focus is on a row; browserless cases fail on the old code; make verify passes."
resolution: null
duplicate_of: null
---
Tree movement keys do nothing after a row is clicked very early in page load.

Found while validating PR #111 in a real browser (pre-existing; reproduces with the arrow keys, not only J/K): clicking a tree row immediately after load, before the keyboard layer has attached, leaves the row focused but ArrowUp/ArrowDown (and J/K) inert until focus moves elsewhere and back.

Suspected cause (unconfirmed): src/metabrowser/static/tree-keyboard-navigation.js repairAnchor calls setAnchor(anchor, false), which never activates the "tree" shortcut scope when the row already holds focus, so the registry's scope stays inactive.

Expected: once the keyboard layer attaches, a tree row that already has focus behaves exactly as if it had been focused afterward — the tree scope is active and movement keys work.

Acceptance: a browserless tree-keyboard session reproduces focus-before-attach (fails today) and passes after the fix; golden or behavior test pins it.
