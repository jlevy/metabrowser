---
type: is
id: is-01m7kp7q43wpwgn8qatzgvqjwr
title: Isolate native provider failures and recover the change relay (D14, R26)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:03.842Z
updated_at: 2026-11-17T02:44:03.842Z
---
Translate pyo3 PanicException (a BaseException) and poisoned-root errors into typed provider failures; the coordinator relay catches only Exception today. Close, reopen, and publish a host reset; extends mb-6o0l. Pin with an injected-failure case. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, D14.
