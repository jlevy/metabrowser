---
type: is
id: is-01m2ysx80jvqzmktna1rf78g5v
title: "PR 140 R3: correct published cache route names in PR summary"
kind: task
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2yrya4k647b005qb2n30n0y
created_at: 2026-09-20T07:01:24.625Z
updated_at: 2026-09-20T15:47:16.833Z
closed_at: 2026-09-20T07:15:56.832Z
close_reason: "Updated PR 140 summary to the registered cache routes: layout, sources, source/{slug}, stores."
resolution: null
duplicate_of: null
---
PR 140 body still advertises /api/cache/entries and /api/cache/entry/{slug}. Actual registered routes are layout, sources, sources/{slug}, stores. Reconcile summary with route registry and parity map.

## Notes

2026-09-20 correction: the description above says the actual registered routes are
"layout, sources, sources/{slug}, stores". The single-source route is singular:
/api/cache/source/{slug}, registered at src/metabrowser/cache/routes.py:80
(Route("/api/cache/source/{slug}", api_cache_source)); /api/cache/sources is the
collection route (routes.py:79). The close reason on this bead already states the
singular form correctly; only the description was wrong.
