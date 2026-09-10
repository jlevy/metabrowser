---
type: is
id: is-01m263m6mg0z3mm3d5brx82mpb
title: Collapse duplicate rollup retry ownership
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-09-10T16:50:13.263Z
updated_at: 2026-09-10T17:49:01.360Z
closed_at: 2026-09-10T17:49:01.359Z
close_reason: "Completed in 632f74bc: the provider read boundary now owns the single snapshot fallback and reports discarded optimistic work in returned and cumulative metrics. The collision regression proves two reducer calls and one logical request."
resolution: null
duplicate_of: null
---
A mutation during the optimistic API rollup can run build_rollup three times: rollup() retries from a snapshot, then the provider read boundary rejects the original header and snapshots again. Give the provider boundary sole retry ownership for API reads, preserve direct store.rollup correctness, and include discarded-attempt work and timing in the returned and cumulative boundary metrics.
