---
type: is
id: is-01m1b5mzft281epbec7m4mmca0
title: "API envelope contract: a generated schema the CLI can show"
kind: epic
status: open
priority: 2
version: 16
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels:
  - Improvement
dependencies: []
parent_id: is-01m26hjjvhpcf49p2x1c3390kk
child_order_hints:
  - is-01m1b5n06x1efn3vrrg79q5ge0
  - is-01m1b5n0k5zcehw2t11sxrpayv
  - is-01m1b5n0zs32tdr8rhy1x6wzjc
  - is-01m1b5n1awje3r2enbetszw8kx
  - is-01m1b5n1pcdr1bddysec15x2mr
  - is-01m1cda2sjv8sg4699t9g9yvs7
  - is-01m1cda35c0ppjyfe07hteh2pq
created_at: 2026-08-31T05:46:06.201Z
updated_at: 2026-11-25T03:58:36.684Z
duplicate_of: null
extensions:
  linear:
    id: deb20028-0e7e-4533-a9ac-d3390d1da4e3
    linked_at: 2026-11-20T19:16:29.260Z
---
The /api/ envelopes are declared as TypedDicts in wire_models.py and git/wire.py, with validate\_\* functions for the tree, rollup, and Git families, and in cache/wire.py, source_routes.py, root_identity.py, and the GitHub plugin's route modules. That contract is invisible outside Python and unreachable from the CLI built to make every model inspectable, and the map document describes each envelope in prose that nothing checks. Generate JSON Schema from the TypedDicts, validate the goldens against it, and serve it. The gating decision is closed (mb-d7ne): /api/ stays an internal contract, described but not published. Plan: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md.

## Notes

2026-11-20 audit: Generated schema for the API envelopes; every child is open.
