---
type: is
id: is-01m2gb3gpn7vcsw0as4xa243tg
title: Stabilize the test suite under machine load before v0.10.0
kind: bug
status: in_progress
priority: 1
version: 3
labels:
  - testing
dependencies: []
child_order_hints:
  - is-01m2gb3pfd368gdf1ragzqezbg
created_at: 2026-09-14T16:13:19.443Z
updated_at: 2026-09-14T16:13:26.428Z
---
Sweep the full pytest suite and tryscript goldens under heavy machine load (load average 7-50 from an unrelated workload, plus CPU burners where quiet). Classify each failure as load/timing flake, real bug, or order dependence, and fix flakes by asserting the product guarantee with deterministic coordination rather than wall-clock thresholds. Starts from the known flake in tests/test_serve_open_race.py (failed once in make verify at load ~40).
