---
type: is
id: is-01m8ctwg96cn7j3rxqnyprcp7y
title: Diagnose why the first Pulls list paint does not converge
kind: bug
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/908
    at: 2026-11-27T00:01:59.793Z
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-26T21:06:20.062Z
updated_at: 2026-11-27T00:01:59.840Z
---
Revision 6 on b38b2ca33 measured a /pulls first useful frame, then failed its settled list/prompt criterion during a catalog refresh. Reproduce with fresh state and current pinned PRs. Identify whether the visible list is lost or the readiness predicate is reading secondary preparation. Keep the existing evidence guard through the diagnosis.

## Notes

Exp-117 reproduced a usable Pulls list and prompt with 25 rows while only the aria-hidden change-count badge was pending. The first-visit guard now distinguishes it from blocking list work, still records its frames, and uses a separate comparison regime. The Chrome fixture and the first live exp-118 list step passed.
