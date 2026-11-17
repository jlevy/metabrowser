---
type: is
id: is-01m7kp7qf40tbnx48zc2myjcbr
title: Provider-selectable harnesses, discovery seams, and per-provider goldens (R12, R13)
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
created_at: 2026-11-17T02:44:04.196Z
updated_at: 2026-11-17T02:44:05.269Z
---
Select the provider for tests/inventory_harness.py and the conformance registry from the environment; replace monkeypatches of walk_tree, MAX_ASSEMBLED_ROWS, and build_rollup with provider-owned seams; run goldens per provider with a named placeholder. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md.
