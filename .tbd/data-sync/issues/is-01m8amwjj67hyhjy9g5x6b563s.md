---
type: is
id: is-01m8amwjj67hyhjy9g5x6b563s
title: "Collection API in softschema (upstream): scan, bind, validate, repair, describe, refresh"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8amwjx1z7rpzb8emdknjxk1
parent_id: is-01m8amwhv15ckjw7prckfmmggr
created_at: 2026-11-26T00:43:02.086Z
updated_at: 2026-11-26T00:43:02.432Z
---
Phase 2, built in jlevy/softschema under its own spec and parity process: tree scan with sniff, pointer-then-contract-index schema binding, batch validation with prepared validators, record states with in-memory repair/conform, field model extending SchemaView, serializable index with incremental refresh, and a CLI over a folder.
