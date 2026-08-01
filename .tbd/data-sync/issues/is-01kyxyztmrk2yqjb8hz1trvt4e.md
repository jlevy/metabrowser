---
type: is
id: is-01kyxyztmrk2yqjb8hz1trvt4e
title: "Spike 4: build the headless local search controller"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxz015gerf8zaryhqej89f8
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:08:10.391Z
updated_at: 2026-08-01T07:02:03.650Z
closed_at: 2026-08-01T07:02:03.649Z
close_reason: Added the DOM-independent provider runtime with request identity, abort cancellation, late-batch rejection, deterministic composition, bounded/yielding local search, and headless no-network tests; make verify passes.
---
Use TDD to add the DOM-independent search controller and local filename provider. Model request identity, AbortSignal cancellation, completeness and truncation separately, stable path deduplication, bounded top results, and late-result rejection. Search catalog snapshots in yielding chunks when measurement requires it and preserve deterministic rank ordering. Add headless contract tests proving the provider runs without palette DOM, obsolete queries cannot publish, and Phase 1 performs no server search request.
