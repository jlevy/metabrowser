---
type: is
id: is-01m1z8mvs8aqkqvt4kv3mxd74j
title: Investigate intermittent multi-second file opens with paired backend measurements
kind: bug
status: open
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-09-08T01:03:16.774Z
updated_at: 2026-09-08T01:24:58.949Z
---
User observed 2.2-2.9 second file navigation with 1.7 seconds reported server time on the reviewed top branch. Compare exact file requests, cheap event-loop probes and concurrent inventory work against main on the same repository without browser rendering. Record system contention, response equivalence and latency distributions; fix any reproducible regression.

## Notes

Browser-free comparison completed on 2026-09-07: main aeef188a versus candidate 96638a7a, two A-B-B-A experiments with fresh processes serving the same repository (13704 files), gzip, 2244 measured successful requests, file-content hashes and catalog completion verified. Ordinary warm medians: main Markdown/Python 6.19/5.11 ms, candidate 3.83/3.28 ms; conditional responses main 3.24/3.08 ms, candidate 2.14/1.86 ms. Eight-client mixed medians: main 28.08/36.24 ms, candidate 68.53/66.70 ms. Follow-up mixed-query ablation suggests Recent contributes but host load confounds attribution. Multi-second stalls occurred on both versions; the stressed follow-up reached about 17 seconds on the candidate, including about 9 seconds for a cheap route probe. First Markdown render ranged 0.77-4.23 seconds on main and 0.80-5.38 seconds on candidate. Host snapshot: 10 logical cores, zero CPU idle, load about 110, 13 GiB compressed memory. Server-Timing is wall time, not CPU. No code changed and no performance-equivalence claim is justified. Keep open for a quieter-host rerun and CPU/queue profiling before final performance sign-off; coordinate with mb-5no9. Raw sanitized evidence is retained locally as metab-backend-comparison-2026-09-07.json, with scratch runners reusing devtools.bench_serving.Server.
