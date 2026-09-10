---
type: is
id: is-01m0nyymwr89c5pmekk6bx3bt8
title: "H48: audit shared index state for a free-threaded build"
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-23T00:04:59.928Z
updated_at: 2026-09-10T17:49:02.085Z
closed_at: 2026-09-10T17:49:02.084Z
close_reason: "Completed by the release-readiness audit: shared inventory, rollup, watcher, catalog, HTTP teardown, and task ownership paths were exercised on CPython 3.14.7t. The final exact-commit make verify run passed all 1,917 tests."
resolution: null
duplicate_of: null
---

## Notes

Release-gate evidence at 19e90b00: make verify under uv-selected CPython 3.14.7+freethreaded collected 1,901 tests and failed 4. The reproducible blocker is tests/test_bench_navigation.py::test_tiny_real_server_workload_is_read_only_and_complete: /api/rollup returned HTTP 500 with KeyError for a directory added between subtree aggregation and bounded-tree emission. Full-run companions were watcher/catalog event timing failures and duplicate simultaneous rollup computation. Existing _rollup_view relies on GIL-era live dict reads. Implementation tracked by mb-126y.
