---
type: is
id: is-01m0t65vgar07vys3fqmqnd0t5
title: Verify rebased provider architecture and performance gates
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - validation
dependencies:
  - type: blocks
    target: is-01m0t661ktb4yqxj6fn392dm9w
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:28:13.833Z
updated_at: 2026-08-24T15:34:03.762Z
---
Run source-naming and focused provider, startup, catalog, inline-tree, rollup, and browser tests; run make format, make lint-check, make test, and the required make verify gate. Audit the final diff against origin/main for lost PR 73 performance/stability behavior and stale underscore asset references.
