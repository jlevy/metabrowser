---
type: is
id: is-01m0w16vgcdqa09w723c9thdmb
title: "PR #74 scope audit S9: make paged conformance test honor version invalidation"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:39:52.587Z
updated_at: 2026-08-25T08:39:52.587Z
---
The provider conformance test for paged time-dependent reads assumes a pinned version remains retained, but watcher delivery legitimately advances the Python provider between pages and the contract requires VersionUnavailableError in that case. The race reproduces locally. Restart bounded assembly on version invalidation while retaining one as_of_ns across attempts, matching the production assembler semantics.
