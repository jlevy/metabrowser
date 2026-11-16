---
type: is
id: is-01m7jp04rw41ezxmwymds6e41m
title: "Hover cards show change counts in the summary's style: '10 A, 5 D, 4 M · +1,234 −567' with bold numbers, status-colored letters, muted punctuation"
kind: task
status: open
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T17:20:41.243Z
updated_at: 2026-11-16T17:32:09.287Z
---
From #479: the hover card lists M, A, D order and tints the added and deleted counts with status inks, unlike the Diff summary's '10 A, 5 D, 4 M'. Ask the owner whether it should match.

## Notes

Owner, 2026-11-16: "any hover styling should match the summary styling". Decided: every hover card that shows change counts (the Commits tab's commit hover card '28 M 4 A files' and any other) uses the Diff summary's count parts and painter. Folded into #479's addressing round (same shared helpers).
