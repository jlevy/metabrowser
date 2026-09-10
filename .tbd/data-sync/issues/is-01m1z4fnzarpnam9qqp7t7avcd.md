---
type: is
id: is-01m1z4fnzarpnam9qqp7t7avcd
title: Profile remaining first catalog and warm serving overhead against main
kind: task
status: open
priority: 2
version: 7
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:50:32.681Z
updated_at: 2026-09-10T17:49:25.269Z
---
Paired same-corpus comparison against main aeef188a on 2026-09-07: 60k first catalog response 73 ms to 281 ms; project-shaped first catalog 4.4 ms to 26 ms; several warm endpoints add single-digit milliseconds. Scan time, CPU and RSS improve substantially, and browser navigation/search remains usable. Profile materialization, validation and thread handoff costs before changing the contract or adding more caches; preserve coherent pages and conditional-response fast paths. Repeat measurements without concurrent test activity and retain both absolute latency and work counters.

## Notes

Correction: historical September 7 and initial September 8 paired comparisons used free-threaded Python for main versus regular Python for the candidate and cannot establish code-only scaling regressions. Controlled September 8 ABBA runs now use identical regular CPython 3.14.6 and dependency versions. On 13709 files after the compact Recent fix, ordinary file medians are about 2 ms on both, Python file median under 8-client Recent contention is 41.04 ms candidate versus 36.98 ms main, with p95 60.96 versus 60.47 ms. First catalog adds about 2.3 ms (5.11 versus 2.82). Retain as nonblocking follow-up for matched-runtime large-corpus scaling and small residual serving overhead; old 60k numbers are explicitly qualified in the review. Reproduce with devtools.bench_navigation; evidence is docs/project/reviews/evidence/navigation-serving-2026-09-08.json. Preserve coherent projections, validation and single ownership; no speculative caches.

The exact v0.9.1 comparison in exp-031 adds two residuals to this follow-up. Cold headed Chrome FCP moved from a 112 ms median to 232 ms while every hard responsiveness gate passed; investigate shell timing without weakening the deferred KPress boundary. Future performance work should also cover directory-heavy, heavily ignored, and representative project trees rather than relying only on the current synthetic corpus. The tested 16 ms inventory-yield variant was rejected because it added scheduling churn without a release-level benefit.
