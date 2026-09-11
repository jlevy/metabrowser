---
type: is
id: is-01m26wh00p5dkkg8m9dcnzmkq9
title: Make lazy browser asset pipelines transactional and ownership-safe
kind: bug
status: closed
priority: 1
version: 2
labels:
  - release-hardening
  - browser
dependencies: []
parent_id: is-01m26s72hwqbm3076hxa0p5z4c
created_at: 2026-09-11T00:05:22.579Z
updated_at: 2026-09-11T00:24:43.483Z
closed_at: 2026-09-11T00:24:43.470Z
close_reason: Implemented ownership-safe lazy asset loading, transactional source append, parallel compositor/chart loading, per-entry bundle retry, and exact browserless regressions
resolution: null
duplicate_of: null
---
Fix final-review findings in file navigation, source append, and chart loading: share successful bundle entries across retries; overlap data and assets; guard same-path ABA on success and failure; make fallback source-cache advancement commit atomically with staged view replacement; and cover failures/concurrency with exact production-module browserless tests.
