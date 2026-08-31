---
type: is
id: is-01m1cda35c0ppjyfe07hteh2pq
title: Decide whether to tighten the tree and rollup declarations
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-30-api-schema-and-contract.md
labels: []
dependencies: []
parent_id: is-01m1b5mzft281epbec7m4mmca0
created_at: 2026-08-31T17:19:12.555Z
updated_at: 2026-08-31T17:19:12.555Z
---
DirNode is total=False with children: list[Any], so TypeAdapter emits no required and an unconstrained children array -- verified. That looseness is deliberate: total=False covers keys whose presence varies, and a child may be a directory or a file. Tightening it is a contract change, not a documentation detail, and needs its own justification plus a check that no producer violates the tightened shape.
