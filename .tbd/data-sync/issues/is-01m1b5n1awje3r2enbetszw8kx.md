---
type: is
id: is-01m1b5n1awje3r2enbetszw8kx
title: Validate every golden envelope against its generated schema
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies:
  - type: blocks
    target: is-01m1b5n0zs32tdr8rhy1x6wzjc
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T05:46:08.091Z
updated_at: 2026-08-31T06:40:36.719Z
---
Validate every golden transcript's envelope against its generated schema. This is what ties the CLI and the API to one structure: a transcript already holds a real captured response, so checking it against the schema proves the schema describes what the server sends rather than what someone believed it sent.

Ordered before the /api/schema route deliberately. A schema nothing checks is a second description that can drift from the first, which is the failure this plan exists to fix; the artifact should be known to match real responses before a route offers it to anyone.
