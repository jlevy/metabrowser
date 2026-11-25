---
type: is
id: is-01m89509228xmhcgxvy9j4nwd5
title: "main red after #835: files totals Chrome check, filter-controls.js failed case never shows the tree"
kind: bug
status: open
priority: 0
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T10:46:11.775Z
updated_at: 2026-11-25T10:46:11.775Z
---
Main run 45596649361 at b26eb4180 (the #835 merge) fails chrome 1/4 on all four interpreters: tests/test_files_totals_stable_chrome.py:260, failOpen case 'ignored filter controls failed 300px light: the tree was never shown' (barPending true, settled false, shownAfter 1036). Deterministic. Likely from #835's change to filter-controls.js (the menus stub / bind changes) breaking the bounded hold when filter-controls.js fails to load. Fix forward or revert #835.
