---
type: is
id: is-01m1z8mvs8aqkqvt4kv3mxd74j
title: Fix Recent-query latency regression against origin/main
kind: bug
status: in_progress
priority: 1
version: 7
labels: []
dependencies: []
created_at: 2026-09-08T01:03:16.774Z
updated_at: 2026-09-08T21:11:16.040Z
---
User observed 2.2-2.9 second file navigation with 1.7 seconds reported server time on the reviewed top branch. Compare exact file requests, cheap event-loop probes and concurrent inventory work against main on the same repository without browser rendering. Record system contention, response equivalence and latency distributions; fix any reproducible regression.

## Notes

Correction: prior paired measurements used CPython 3.14.7+freethreaded for main versus regular 3.14.6 for the branch; they do not establish a code-only regression. Rebuilt baseline with the exact candidate interpreter. Matched-runtime thread CPU profiling with 5000 rows and identical include_ignored=True finds selection plus serialization at 24.19 ms candidate versus 7.60 ms main. Dominant added work is full InventoryEntry construction; coordinator also decorates Recent rows that the API discards. Implementing compact validated RecentRecord rows and distinct-ancestor traversal, plus a durable CLI benchmark that checks interpreter identity before comparing builds. Previous runtime-confounded numbers will be qualified in the review and PR.
