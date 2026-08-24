---
type: is
id: is-01m0t8q4hrp2rk7yzcmh33bny4
title: Restore catalog route regression coverage after provider migration
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - testing
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:12:37.303Z
updated_at: 2026-08-24T16:12:37.303Z
---
The provider migration consolidated catalog tests but dropped PR 73's explicit incomplete-while-discovering route assertion and its structural proof that catalog wire dictionaries are built only inside the off-loop encoder. Restore those checks through the runtime/provider harness without coupling the route to Python-provider internals.
