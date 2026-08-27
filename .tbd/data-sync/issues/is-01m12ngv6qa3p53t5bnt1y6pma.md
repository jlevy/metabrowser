---
type: is
id: is-01m12ngv6qa3p53t5bnt1y6pma
title: Coordinate the Changes header with the Git panel tally and summary request
kind: feature
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-27T22:30:18.070Z
updated_at: 2026-08-27T23:15:07.060Z
closed_at: 2026-08-27T23:15:07.059Z
close_reason: "Decided in 65af050 and 0715a66: Changes and History each own a header, stacked, rather than sharing one region — the counts answer different questions and go stale independently, and merging them would put a status count above the scroll origin History needs to keep. Request ordering fixed: status and the first history page together, then /api/git/summary once the first page is on screen."
resolution: null
duplicate_of: null
---
Two collisions between the Git-status plan and what landed with #86 plus the header tally, both in docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md. (1) The plan puts counts, a Clean state, and manual refresh in a Changes header, while the panel now has .git-history-summary holding the history tally; the plan must say whether these are one header region or two stacked ones, and the design-system section must register whichever it picks. (2) The plan says status and the first history page load concurrently on first show, but there is now a third lazy request — /api/git/summary — deliberately deferred until after the first page paints so its graph traversal does not block rendering. State the intended ordering for all three so status does not reintroduce the contention the summary deferral exists to avoid.
