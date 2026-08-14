---
type: is
id: is-01m00nzbv28s9cd2qjykjfdp8w
title: Render folder rollup views only from complete snapshots
kind: bug
status: open
priority: 1
version: 2
labels:
  - browser
  - folder-overview
dependencies:
  - type: blocks
    target: is-01m00prch1akzeds6rnwc4rkwy
parent_id: is-01m00nzbe12ws4pm4870qgr3q1
created_at: 2026-08-14T17:44:03.169Z
updated_at: 2026-08-14T17:57:43.072Z
---
Folder overview-derived views currently expose provisional rollup values while indexing, so users see zero counts and partial tables or treemap geometry that later change.

Required behavior:
- Treat rollup data as an atomic snapshot for the requested directory and active view options.
- While that snapshot is unavailable or still indexing, render the same quiet pulsing block vocabulary used by pending nav-panel tally cells.
- Apply this consistently to the Files summary, treemap, and future rollup-backed overview panels through a shared readiness/loading contract rather than view-specific timing guesses.
- Never render temporary zero totals, partial type rows, partial treemap cells, or a premature empty-directory state.
- Transition directly from pending to the complete snapshot; stale responses from a prior path or option selection must not replace the current view.
- Once indexing is complete, an actually empty directory must render its normal stable empty state.
- Preserve explicit error behavior and existing reduced-motion treatment.

Validation:
- Add behavioral tests for in-progress, complete, empty, error, and rapid-navigation or stale-response transitions.
- Verify both Files and treemap views use the shared loading treatment and publish no partial rollup content.
- Run the relevant browser tests and the repository verification gate before handoff.
