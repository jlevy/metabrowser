---
type: is
id: is-01m1z8mvs8aqkqvt4kv3mxd74j
title: Fix Recent-query latency regression against origin/main
kind: bug
status: closed
priority: 1
version: 9
labels: []
dependencies: []
created_at: 2026-09-08T01:03:16.774Z
updated_at: 2026-09-08T21:45:27.443Z
closed_at: 2026-09-08T21:45:27.441Z
close_reason: Fixed in 37011c44 and pushed to the top inventory PR. Full make verify passes 1901 tests and 99 goldens, both vulnerability audits, distribution inspection and installed-wheel smoke. All six CI checks passed at run 34282011816, including Python 3.12/3.13/3.14 and complete-stack integration with main. Browser validation on the committed code passed Markdown/Python opens, Quick File, the 5000-row Recent view, back/forward, filter restoration and reload with no new warnings/errors. Controlled performance evidence and the runtime-mismatch correction are committed; small residual serving/scaling work remains in mb-5no9.
resolution: null
duplicate_of: null
---
User observed 2.2-2.9 second file navigation with 1.7 seconds reported server time on the reviewed top branch. Compare exact file requests, cheap event-loop probes and concurrent inventory work against main on the same repository without browser rendering. Record system contention, response equivalence and latency distributions; fix any reproducible regression.

## Notes

Fixed the measured cause with compact validated RecentRecord rows, no unused coordinator decoration join, and distinct-ancestor traversal; no cache or full-index mirror. Controlled regular CPython 3.14.6 ABBA comparisons against unchanged main aeef188a served the same 13709 files with identical development dependencies and passed 3752 measured response checks. Python file median with Recent: before 62.70 ms (main 39.74), after 41.04 (main 36.98); p95 after 60.96 versus 60.47 ms. Markdown median after 41.25 versus 37.49. Recent workload CPU drops from 1.27-1.30 seconds to 0.82-0.83 per 20 bursts. Ordinary reads around 2 ms; residual roughly 4 ms contention cost remains in nonblocking mb-5no9. Durable CLI devtools.bench_navigation checks runtime/GIL identity, dependency versions, code hashes, statuses, indexed population, file content and catalog/Recent membership; raw samples and summaries go to JSON. Review and evidence corrected for prior mismatched-runtime claims. Full make verify passed 1901 tests, 99 goldens, both audits, distribution and installed wheel after development HTTPX2 security upgrade; commit/push, CI and final browser check pending.
