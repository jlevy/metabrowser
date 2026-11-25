---
type: is
id: is-01m8a22ybhrr9280chpfmv29n5
title: "Ages end the row: Conversation commit rows, guide commit note"
kind: task
status: open
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-11-25T19:14:27.824Z
updated_at: 2026-11-25T20:07:12.665Z
---
The design-system rule "Ages End the Row" (docs/design-system.md, added in PR #843) says: in a list row, a timestamp or age is right-aligned at the row's end, so a list's ages read as one column. Exceptions: inline prose, a page header's metadata line, a single-line item with no column; a table's own time column counts as a column. An audit for PR #843 found these list rows that break it:

1. Conversation commit rows on a pull request's page (src/metabrowser/builtin_plugins/github/pull-page.js near 6642-6651, styles near github/styles.css 774-791): subject, "committed <age>", then the short ID, so the ID ends the row and the age is second to last. The row also wraps on narrow panes. The fix is swapping two children plus tests (five test files name these classes).
2. A guide's commit row whose commit this copy cannot open (guided-review.js `commitRow`): "Not in this checkout." follows the age.

Not a violation (user decision, 2026-11-25): Files tab tree rows keep the age after the name and the size or count chip ending the row, because a file's size is more valuable right-aligned, where a folder's sizes read as one column. The rule's doc records this exemption.

Already compliant (verified): Commits tab rows (`.git-graph-age`), ref selector rows (`.source-ref-selector-age`), agents session rows (`.agents-row-age`), the agents session event list, the guide's commit row, and the Pulls row (PR #843). Tables keep their time in a column: the agents Sessions table and the event log rows.

## Notes

User decision 2026-11-25: when a row shows a size and an age, the size ends the row right-aligned; only age-without-size rows end with the age. Files tree rows keep their layout. Recorded in design-system.md by PR #849.
