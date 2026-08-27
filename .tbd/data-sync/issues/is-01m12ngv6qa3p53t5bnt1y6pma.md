---
type: is
id: is-01m12ngv6qa3p53t5bnt1y6pma
title: Coordinate the Changes header with the Git panel tally and summary request
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-27T22:30:18.070Z
updated_at: 2026-08-27T22:30:18.070Z
---
Two collisions between the Git-status plan and what landed with #86 plus the header tally, both in docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md. (1) The plan puts counts, a Clean state, and manual refresh in a Changes header, while the panel now has .git-history-summary holding the history tally; the plan must say whether these are one header region or two stacked ones, and the design-system section must register whichever it picks. (2) The plan says status and the first history page load concurrently on first show, but there is now a third lazy request — /api/git/summary — deliberately deferred until after the first page paints so its graph traversal does not block rendering. State the intended ordering for all three so status does not reintroduce the contention the summary deferral exists to avoid.
