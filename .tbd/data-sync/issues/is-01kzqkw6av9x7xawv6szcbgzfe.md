---
type: is
id: is-01kzqkw6av9x7xawv6szcbgzfe
title: "PR 28 review R11: cleared recency window makes the overlay cutoff NaN"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzqkvjhnr72wwk0cz3pmq7zp
created_at: 2026-08-11T05:14:12.186Z
updated_at: 2026-08-11T05:26:27.724Z
closed_at: 2026-08-11T05:26:27.723Z
close_reason: Overlay bails when no window is active and the guard tests for a number. Verified in-browser; fixed in b37c6dd.
---
src/metabrowser/static/app.js recentBaseApplyOp reads _RECENT_WINDOW_SECONDS[currentRecentWindow]. Leaving the recency source sets that to the empty string, so the lookup is undefined; the guard tests !== null, undefined passes it, and the cutoff becomes NaN. Every comparison against NaN is false, so no upsert is ever dropped and recentBaseEntries grows without bound while the plain tree is on screen.
