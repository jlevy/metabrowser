---
type: is
id: is-01m2f00h5wzq5fprgnv5r8wxcy
title: "PR #111 review R2: Git commit row keys depend on keyboard-shortcuts.js load order, unpinned"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2f006s6gd550e7knf1qw3m6
created_at: 2026-09-14T03:40:12.859Z
updated_at: 2026-09-14T04:22:37.087Z
closed_at: 2026-09-14T04:22:37.086Z
close_reason: "Fixed in e277e7a9 (PR #111), option (a): dropped the unreachable isEditableTarget check and foreign-target test loop; the Git DOM test loads the panel without keyboard-shortcuts.js."
resolution: null
duplicate_of: null
---
PR #111 review R2 (Low). src/metabrowser/static/git-panel.js:1246 commitRowKey calls window.MetabrowserKeyboardShortcuts.isEditableTarget; tests/test_git_e2e.py:195 does not pin keyboard-shortcuts.js before git-panel.js; the editable check cannot trigger on a commit row. Fix (pick one): (a) drop the check and the foreign-target loop at tests/dom/git-panel-behavior.js:1596, or (b) pin the load order.
