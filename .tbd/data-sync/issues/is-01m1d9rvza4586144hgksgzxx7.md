---
type: is
id: is-01m1d9rvza4586144hgksgzxx7
title: "Flaky: simultaneous rollup coalescing test fails under load"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-09-01T01:36:36.841Z
updated_at: 2026-09-01T01:36:36.841Z
---
tests/test_rollup_route.py::test_simultaneous_identical_rollups_compute_once asserts that six concurrent /api/rollup requests call build_rollup exactly once. It failed once in four full-suite runs on the merged inventory-engine stack and passes in isolation every time.

Likely mechanism: the assertion is a single-flight guarantee keyed on the engine version and request shape. While inventory_harness is still settling, a late watcher event can advance the engine version mid-gather, splitting the six requests across two cache keys and producing two builds. Nothing is wrong with the coalescing; the test asserts a deterministic outcome for a race it does not pin.

Options: settle the harness to a quiescent version before gathering, or assert 'fewer than six builds' plus identical bodies, which is what coalescing actually promises. Prefer the first, since the current assertion is the stronger and more useful one when it can be made deterministic.

Same class as the event-loop stall test fixed in 'test: measure the loop stall, not the machine it ran on' -- a timing assertion measured on a loaded machine.
