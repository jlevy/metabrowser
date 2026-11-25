---
type: is
id: is-01m8a22ybhrr9280chpfmv29n5
title: "Ages end the row: Files tree rows, Conversation commit rows, guide commit note"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T19:14:27.824Z
updated_at: 2026-11-25T19:14:27.824Z
---
The design-system rule "Ages End the Row" (docs/design-system.md, added in PR #843) says: in a list row, a timestamp or age is right-aligned at the row's end, so a list's ages read as one column. Exceptions: inline prose, a page header's metadata line, a single-line item with no column; a table's own time column counts as a column. An audit for PR #843 found these list rows that break it, left out of #843 because each restructures a row and its tests:

1. Files tab tree rows (src/metabrowser/static/app.js file/folder/symlink builders near 2584-2722, the live-insert copies near 8035-8160, the patcher near 7942-7987): the age, `.tree-item-age-inline` (styles.css near 3821), sits right after the name, and the size/count chip ends the row (`.tree-item-size`, `margin-left: auto`). Making the age end the row means reordering six builders and the patcher, plus their tests; deciding whether the size or the age ends the row is a design call.
2. Conversation commit rows on a pull request's page (src/metabrowser/builtin_plugins/github/pull-page.js near 6642-6651, styles near github/styles.css 774-791): subject, "committed <age>", then the short ID, so the ID ends the row and the age is second to last. The row also wraps on narrow panes. The fix is swapping two children plus tests (five test files name these classes).
3. A guide's commit row whose commit this copy cannot open (guided-review.js `commitRow`): "Not in this checkout." follows the age.

Already compliant (verified): Commits tab rows (`.git-graph-age`), ref selector rows (`.source-ref-selector-age`), agents session rows (`.agents-row-age`), the agents session event list, the guide's commit row, and the Pulls row (PR #843). Tables keep their time in a column: the agents Sessions table and the event log rows.
