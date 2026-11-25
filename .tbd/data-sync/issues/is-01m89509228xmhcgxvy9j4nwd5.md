---
type: is
id: is-01m89509228xmhcgxvy9j4nwd5
title: "main red after #835: files totals Chrome check, filter-controls.js failed case never shows the tree"
kind: bug
status: closed
priority: 0
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/839
    at: 2026-11-25T10:55:44.617Z
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T10:46:11.775Z
updated_at: 2026-11-25T11:12:16.493Z
started_at: 2026-11-25T10:46:32.520Z
closed_at: 2026-11-25T11:12:16.492Z
close_reason: "Fixed forward in #839: the shell feature-detects metabrowser.menus, so a load whose filter-controls.js failed starts again; pinned in the unit tier"
resolution: null
duplicate_of: null
---
Main run 45596649361 at b26eb4180 (the #835 merge) fails chrome 1/4 on all four interpreters: tests/test_files_totals_stable_chrome.py:260, failOpen case 'ignored filter controls failed 300px light: the tree was never shown' (barPending true, settled false, shownAfter 1036). Deterministic. Likely from #835's change to filter-controls.js (the menus stub / bind changes) breaking the bounded hold when filter-controls.js fails to load. Fix forward or revert #835.
