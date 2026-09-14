---
type: is
id: is-01m1d9rvza4586144hgksgzxx7
title: "Flaky: simultaneous rollup coalescing test fails under load"
kind: bug
status: closed
priority: 3
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01m2fafd1v8d5pakt6r7zxw5n8
created_at: 2026-09-01T01:36:36.841Z
updated_at: 2026-09-14T08:06:17.863Z
closed_at: 2026-09-14T08:06:17.862Z
close_reason: "Fixed in https://github.com/jlevy/metabrowser/pull/119: test_simultaneous_identical_rollups_compute_once runs the harness with watch_mode=off so the settled version is quiescent by construction, and asserts the engine version is unchanged across the gather before asserting one build. A late filesystem change injected mid-gather fails the old test 30/30 (2 builds) and passes the new one 30/30; disabling the in-flight registry fails it with 6 builds."
resolution: null
duplicate_of: null
---
tests/test_rollup_route.py::test_simultaneous_identical_rollups_compute_once asserts that six concurrent /api/rollup requests call build_rollup exactly once. It failed once in four full-suite runs on the merged inventory-engine stack and passes in isolation every time.

Likely mechanism: the assertion is a single-flight guarantee keyed on the engine version and request shape. While inventory_harness is still settling, a late watcher event can advance the engine version mid-gather, splitting the six requests across two cache keys and producing two builds. Nothing is wrong with the coalescing; the test asserts a deterministic outcome for a race it does not pin.

Options: settle the harness to a quiescent version before gathering, or assert 'fewer than six builds' plus identical bodies, which is what coalescing actually promises. Prefer the first, since the current assertion is the stronger and more useful one when it can be made deterministic.

Same class as the event-loop stall test fixed in 'test: measure the loop stall, not the machine it ran on' -- a timing assertion measured on a loaded machine.
