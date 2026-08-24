---
type: is
id: is-01m0t8bsb54j16rhfdmwj5q0vh
title: Audit backend delivery and scheduling invariants from PR 73
kind: task
status: open
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies:
  - type: blocks
    target: is-01m0t8c0dr9dc0xkz1kvw6dya1
parent_id: is-01m0t88jfkvafypd9h2sgvfz6p
child_order_hints:
  - is-01m0t8q47y0evpx16xrxfpr036
  - is-01m0t8q4hrp2rk7yzcmh33bny4
  - is-01m0t904abpj64gs33921yh9j2
  - is-01m0t91hpmqkhcqgmfckmnp6fm
  - is-01m0t9dbjv2mvbv26cj8fy1p95
created_at: 2026-08-24T16:06:25.368Z
updated_at: 2026-08-24T16:24:45.402Z
---
Trace PR 73 changes to inventory walking, event-loop yields, catalog invalidation, tree/filter reads, server composition, startup cancellation, and backend benchmarking into the final Python provider/coordinator architecture. Prove each invariant survives or fix it.
