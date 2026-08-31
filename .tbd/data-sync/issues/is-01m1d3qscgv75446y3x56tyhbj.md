---
type: is
id: is-01m1d3qscgv75446y3x56tyhbj
title: Add a provider conformance case for aggregate payload shape
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-31T23:51:09.967Z
updated_at: 2026-08-31T23:51:09.967Z
---
The conformance registry in tests/test_inventory_provider_contract.py covers checkpoints, semantic parity, bounds, paging, version pins, changes, verified refresh, lifecycle, sessions, and joined close. It does not assert the shape of the rollup and navigation payloads.

Those payloads are currently 'list[list[object]]' and 'list[Any]' (see mb-gwlw), so a second provider can satisfy every registered conformance case and still return rows the browser cannot read -- wrong element order in a tally row, nested children instead of the expected node shape, seconds instead of nanoseconds. Nothing in the suite would fail.

Add a factory-parametrized case asserting the aggregate payloads against a fixed fixture tree, so the shape is pinned for every registered backend rather than only for the one that happens to build it today. Register it in PROVIDER_CONFORMANCE_TESTS and in the architecture document's table, which the meta-tests already require.
