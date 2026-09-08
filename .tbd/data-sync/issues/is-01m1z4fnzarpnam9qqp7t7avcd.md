---
type: is
id: is-01m1z4fnzarpnam9qqp7t7avcd
title: Profile remaining first catalog and warm serving overhead against main
kind: task
status: open
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:50:32.681Z
updated_at: 2026-09-08T01:25:07.849Z
---
Paired same-corpus comparison against main aeef188a on 2026-09-07: 60k first catalog response 73 ms to 281 ms; project-shaped first catalog 4.4 ms to 26 ms; several warm endpoints add single-digit milliseconds. Scan time, CPU and RSS improve substantially, and browser navigation/search remains usable. Profile materialization, validation and thread handoff costs before changing the contract or adding more caches; preserve coherent pages and conditional-response fast paths. Repeat measurements without concurrent test activity and retain both absolute latency and work counters.

## Notes

Follow-up user-reported latency investigation mb-ulzy now makes this a performance sign-off item. Earlier paired evidence remains in docs/project/reviews/evidence/inventory-stack-serving-2026-09-07.json. New same-repository A-B-B-A HTTP probes under heavy host contention show comparable ordinary file opens, but mixed eight-client file-open medians of 28-36 ms on main versus 67-69 ms on candidate. Removing Recent queries reduced the apparent difference in a follow-up, suggesting projection/materialization or queue contention; phase order and fluctuating load prevent causal attribution. Both builds also exhibited multi-second outliers, so do not attribute those solely to the refactor or certify parity. Next: repeat on a quiet host and profile CPU, GIL/thread-pool/host-lock wait, and Recent result assembly before changing contracts, adding caches or relaxing limits. Preserve source-content checks, gzip, conditional responses and identical physical corpora.
