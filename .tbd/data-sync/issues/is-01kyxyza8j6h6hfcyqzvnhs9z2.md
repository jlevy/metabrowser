---
type: is
id: is-01kyxyza8j6h6hfcyqzvnhs9z2
title: "Spike 2: build the known-file catalog"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxyztmrk2yqjb8hz1trvt4e
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:07:53.617Z
updated_at: 2026-08-01T06:34:04.638Z
closed_at: 2026-08-01T06:34:04.637Z
close_reason: Added an immutable, partial client-side known-file catalog with adapters for tree, recent, event, and navigation observations; full make verify passes.
---
Use TDD to add a strict known_file_catalog browser module with idempotent path observation, files-only snapshots, source metadata, revisioning, immutable reads, root and resync clearing, and scoped removal. Define explicit adapters for initial tree, complete lazy subtree payloads including unmounted pages, Recent, event snapshots and changes, and successful direct navigation. Phase 1 metadata must always report incomplete local coverage. Keep contents, aggregates, and renderer state out of the catalog.
