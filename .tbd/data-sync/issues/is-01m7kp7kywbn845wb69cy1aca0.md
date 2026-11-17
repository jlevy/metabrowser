---
type: is
id: is-01m7kp7kywbn845wb69cy1aca0
title: Conformance asserts semantics and bounds, not the Python implementation (R1, R2)
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7rgntx2bzfsp2836gyw9
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:00.604Z
updated_at: 2026-11-17T02:44:05.269Z
---
Rewrite the Python-pinning assertions (provider name, admission order, replay granularity, hard directory limit, watch strings, exact rows_visited, watching phase), register the unregistered grouped-tree case with a two-way check, and state and pin the implicit rules and the host coalescing rule. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R1 and R2.
