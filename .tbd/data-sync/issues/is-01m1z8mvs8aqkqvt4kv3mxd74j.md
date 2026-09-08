---
type: is
id: is-01m1z8mvs8aqkqvt4kv3mxd74j
title: Fix Recent-query latency regression against origin/main
kind: bug
status: open
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-09-08T01:03:16.774Z
updated_at: 2026-09-08T16:37:45.745Z
---
User observed 2.2-2.9 second file navigation with 1.7 seconds reported server time on the reviewed top branch. Compare exact file requests, cheap event-loop probes and concurrent inventory work against main on the same repository without browser rendering. Record system contention, response equivalence and latency distributions; fix any reproducible regression.

## Notes

September 8 rerun confirms a consistent mixed-workload regression against unchanged origin/main aeef188a; candidate is 96638a7a. Same physical repository, 13704 files, two A-B-B-A experiments, 2244 successful measured requests with file-content and catalog checks. Ordinary warm medians main/candidate: Markdown 4.62/4.58 ms, Python 4.14/4.96 ms. Seven-client inventory workload WITHOUT Recent: Python 27.79/27.36 ms, Markdown 30.29/32.90 ms. Same experiment WITH Recent (eight clients): Python 35.11/81.98 ms, Markdown 31.90/87.95 ms, Recent 52.16/112.22 ms. Thus the difference appears with Recent and persists across alternating code order; normal file serving and Markdown rendering are comparable. Warm rendering 8.22/7.37 ms, first rendering 248.37/209.15 ms. No multi-second stalls today: slowest measured request 269.88 ms. Host remained busy (load roughly 13-25 on ten cores; 0-4 percent idle), but far below prior load near 110. Prior stressed run and outliers are retained in September 7 evidence. September 8 evidence is retained locally as metab-backend-comparison-2026-09-08.json. Next: profile Recent selection, semantic record construction, coordinator composition and serialization, then remove measured work without weakening canonical identity, tracked-first ordering, coherence or provider ownership. Performance sign-off remains pending; source unchanged during measurement.
