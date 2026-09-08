---
type: is
id: is-01m1z4fnzarpnam9qqp7t7avcd
title: Profile remaining first catalog and warm serving overhead against main
kind: task
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:50:32.681Z
updated_at: 2026-09-08T00:04:35.097Z
---
Paired same-corpus comparison against main aeef188a on 2026-09-07: 60k first catalog response 73 ms to 281 ms; project-shaped first catalog 4.4 ms to 26 ms; several warm endpoints add single-digit milliseconds. Scan time, CPU and RSS improve substantially, and browser navigation/search remains usable. Profile materialization, validation and thread handoff costs before changing the contract or adding more caches; preserve coherent pages and conditional-response fast paths. Repeat measurements without concurrent test activity and retain both absolute latency and work counters.

## Notes

Paired evidence and exact limitations are in docs/project/reviews/evidence/inventory-stack-serving-2026-09-07.json and the September 7 merge-readiness review. This is a post-merge optimization follow-up, not a statistical budget. The older private 300k corpus result has not been reproduced here.
