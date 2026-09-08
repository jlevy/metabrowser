---
type: is
id: is-01m1z4fnzarpnam9qqp7t7avcd
title: Profile remaining first catalog and warm serving overhead against main
kind: task
status: open
priority: 1
version: 5
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:50:32.681Z
updated_at: 2026-09-08T16:37:46.846Z
---
Paired same-corpus comparison against main aeef188a on 2026-09-07: 60k first catalog response 73 ms to 281 ms; project-shaped first catalog 4.4 ms to 26 ms; several warm endpoints add single-digit milliseconds. Scan time, CPU and RSS improve substantially, and browser navigation/search remains usable. Profile materialization, validation and thread handoff costs before changing the contract or adding more caches; preserve coherent pages and conditional-response fast paths. Repeat measurements without concurrent test activity and retain both absolute latency and work counters.

## Notes

September 8 repeated A-B-B-A comparisons against unchanged origin/main confirm the Recent-related contention regression tracked in mb-ulzy. Ordinary file reads and rendering are comparable. In the isolation experiment, file-request medians are comparable without Recent (Python 27.79 ms main, 27.36 ms candidate), but diverge with it (35.11 vs 81.98 ms); Recent itself rises from 52.16 to 112.22 ms. Both versions returned correct content across 2244 measurements; no multi-second outliers recurred, with overall max 269.88 ms. This is stronger evidence than the highly overloaded September 7 run. Keep performance sign-off pending while profiling and fixing the Recent path. The separately measured first-catalog and warm endpoint overhead from docs/project/reviews/evidence/inventory-stack-serving-2026-09-07.json still needs assessment after that fix. Preserve coherence and one owner of facts; do not hide cost with speculative caches or relax validation.
