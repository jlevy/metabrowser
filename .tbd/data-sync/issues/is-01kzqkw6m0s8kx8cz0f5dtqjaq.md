---
type: is
id: is-01kzqkw6m0s8kx8cz0f5dtqjaq
title: "PR 28 review R12: filtered tally goes stale when type or size changes"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzqkvjhnr72wwk0cz3pmq7zp
created_at: 2026-08-11T05:14:12.479Z
updated_at: 2026-08-11T05:26:27.976Z
closed_at: 2026-08-11T05:26:27.976Z
close_reason: Filtered tally recomputed per pass, cache removed. Verified in-browser; fixed in b37c6dd.
---
src/metabrowser/static/app.js _renderFilteredTally reads _recentFilteredCount, which is only recomputed by renderRecentFromBase. Changing type or size under a recency window runs applyTreeFilters alone, so row visibility updates while the count keeps the previous value.
