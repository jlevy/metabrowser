---
type: is
id: is-01m7kp7kywbn845wb69cy1aca0
title: Conformance asserts semantics and bounds, not the Python implementation (R1, R2)
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7rgntx2bzfsp2836gyw9
parent_id: is-01m0r8xt95921dabcddjjm7csf
hold: null
hold_until: null
created_at: 2026-11-17T02:44:00.604Z
updated_at: 2026-11-17T08:36:25.379Z
started_at: 2026-11-17T07:16:26.188Z
closed_at: 2026-11-17T08:36:25.379Z
close_reason: "Delivered in jlevy/metabrowser#507 (decisions record) and #508 (conformance neutrality); #508, which contains both, is CI green. #507's one red test is the pre-existing storage race mb-532r."
resolution: null
duplicate_of: null
---
Rewrite the Python-pinning assertions (provider name, admission order, replay granularity, hard directory limit, watch strings, exact rows_visited, watching phase), register the unregistered grouped-tree case with a two-way check, and state and pin the implicit rules and the host coalescing rule. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R1 and R2.
