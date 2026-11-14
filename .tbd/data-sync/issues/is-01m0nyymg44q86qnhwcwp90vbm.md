---
type: is
id: is-01m0nyymg44q86qnhwcwp90vbm
title: "H47: the 64-worker executor is sized for I/O waiters, not CPU-bound offloads"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T00:04:59.524Z
updated_at: 2026-11-14T18:46:43.164Z
---
Load-time hypothesis H47 (plan-2026-08-21-load-time-performance.md, Hypotheses). The default executor has 64 workers (DEFAULT_EXECUTOR_WORKERS, src/metabrowser/settings.py), sized for I/O waiters. Under one GIL, more workers mean more contention for the CPU-bound tally and encode work now routed through it. Metric: tally and encode latency, and walk time, against pool size.
