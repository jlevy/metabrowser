---
type: is
id: is-01m1z2d4qadv8m3k6qt3wwj40g
title: Make serving benchmarks observe fast scan completion
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:14:12.319Z
updated_at: 2026-09-08T00:02:47.517Z
closed_at: 2026-09-08T00:02:47.515Z
close_reason: Serving harness child processes explicitly enable DEBUG completion logs, independent of parent verbosity. Small corpus integration test completes and both paired project benchmark runs finished.
resolution: null
duplicate_of: null
---
The project-corpus baseline finished scanning but bench_serving waited 600 seconds for a log record suppressed at the default INFO level. Server enables METABROWSER_DEBUG for endpoints but not DEBUG logging; fast scans log completion at DEBUG. Explicitly enable diagnostic logging for benchmark subprocesses, pin with a tiny-corpus integration test, and run both baseline and candidate with the same instrumentation.
