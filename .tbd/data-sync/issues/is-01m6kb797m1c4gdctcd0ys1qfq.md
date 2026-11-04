---
type: is
id: is-01m6kb797m1c4gdctcd0ys1qfq
title: Make QA fetch guarantees distinguish reads from explicit acquisition and refresh
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6jhctf78vq1v7ndv43jzssy
created_at: 2026-11-04T13:15:53.459Z
updated_at: 2026-11-04T13:15:53.459Z
---
Documentation review D13: current QA constraints and one-shot CLI prose universally promise no fetching outside source refresh, omitting initial URL/PR acquisition and explicit GitHub refresh actions. Rewrite around existing-source cache-only GET/read guarantees, explicit acquisition and provider jobs. Preserve no automatic object repair on passive reads and use actual registered action names. This keeps session-based gh assertions meaningful; no runtime change or new benchmark.
