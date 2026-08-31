---
type: is
id: is-01m1b5mzft281epbec7m4mmca0
title: "API envelope contract: a generated schema the CLI can show"
kind: epic
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
child_order_hints:
  - is-01m1b5n06x1efn3vrrg79q5ge0
  - is-01m1b5n0k5zcehw2t11sxrpayv
  - is-01m1b5n0zs32tdr8rhy1x6wzjc
  - is-01m1b5n1awje3r2enbetszw8kx
  - is-01m1b5n1pcdr1bddysec15x2mr
  - is-01m1cda2sjv8sg4699t9g9yvs7
  - is-01m1cda35c0ppjyfe07hteh2pq
created_at: 2026-08-31T05:46:06.201Z
updated_at: 2026-08-31T17:19:12.555Z
---
31 TypedDicts across wire_models.py and git/wire.py define the /api/ envelopes, with 12 validate_* functions. That contract is invisible outside Python and unreachable from the CLI built to make every model inspectable, and the map document describes each envelope in prose that nothing checks. Generate JSON Schema from the TypedDicts, serve it, and validate the goldens against it. One decision is open first: whether /api/ stays an internal contract, which the plan assumes.
