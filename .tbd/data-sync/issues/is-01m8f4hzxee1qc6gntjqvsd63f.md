---
type: is
id: is-01m8f4hzxee1qc6gntjqvsd63f
title: Publish parse and binding progress from the SoftSchema scanner
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
created_at: 2026-11-27T18:33:50.253Z
updated_at: 2026-11-27T18:33:50.253Z
---
SoftSchema 0.10.0 observes discovery through the ignore predicate before parsing. Add a supported, optional aggregate progress callback for discovery, artifact reads and binding, with a parity test that preserves results and supports cooperative cancellation between bounded units. Feed those counters into the shared progress status after the API release. Universe pure cold scan spent 41.8 s inspecting and parsing artifacts after a 0.24 s discovery walk.
