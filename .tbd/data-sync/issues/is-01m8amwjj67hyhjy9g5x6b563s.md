---
type: is
id: is-01m8amwjj67hyhjy9g5x6b563s
title: "Collection API in softschema (upstream): scan, bind, validate, repair, describe, refresh"
kind: task
status: closed
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/softschema/pull/78
    at: 2026-11-26T17:34:43.288Z
  - kind: pr
    url: https://github.com/jlevy/softschema/pull/79
    at: 2026-11-27T09:59:04.944Z
  - kind: other
    url: https://github.com/jlevy/softschema/releases/tag/v0.10.0
    at: 2026-11-27T17:51:52.597Z
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m8amwjx1z7rpzb8emdknjxk1
  - type: blocks
    target: is-01m8cnf4sgyjn4q4psvp77emx2
  - type: blocks
    target: is-01m8cqyztrsa3gpezt5vtm78cx
  - type: blocks
    target: is-01m8cy22wfphaxjvb67txqpm6a
parent_id: is-01m8amwhv15ckjw7prckfmmggr
hold: null
hold_until: null
created_at: 2026-11-26T00:43:02.086Z
updated_at: 2026-11-27T17:51:53.090Z
started_at: 2026-11-26T10:04:06.029Z
closed_at: 2026-11-27T17:51:53.088Z
close_reason: SoftSchema 0.10.0 is published and verified on PyPI and npm. The standard Metabrowser lock upgrade and verification remain tracked in the downstream rollout.
resolution: null
duplicate_of: null
---
Phase 2, built in jlevy/softschema under its own spec and parity process: tree scan with sniff, pointer-then-contract-index schema binding, batch validation with prepared validators, record states with in-memory repair/conform, field model extending SchemaView, serializable index with incremental refresh, and a CLI over a folder.

## Notes

Both language implementations and the scan CLI are on https://github.com/jlevy/softschema/pull/78. All upstream CI checks passed, including release-candidate smoke and cross-engine parity. Stable downstream integration waits for a released dependency.
