---
type: is
id: is-01m2ysx80jvqzmktna1rf78g5v
title: "PR 140 R3: correct published cache route names in PR summary"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2yrya4k647b005qb2n30n0y
created_at: 2026-09-20T07:01:24.625Z
updated_at: 2026-09-20T07:15:56.838Z
closed_at: 2026-09-20T07:15:56.832Z
close_reason: "Updated PR 140 summary to the registered cache routes: layout, sources, source/{slug}, stores."
resolution: null
duplicate_of: null
---
PR 140 body still advertises /api/cache/entries and /api/cache/entry/{slug}. Actual registered routes are layout, sources, sources/{slug}, stores. Reconcile summary with route registry and parity map.
