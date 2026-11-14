---
type: is
id: is-01m1mv9zmvtf5nnr5kjs16vq6k
title: "PR #101 R3.3: provider restart is unrecoverable"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0r8xt95921dabcddjjm7csf
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-09-03T23:57:44.474Z
updated_at: 2026-11-14T18:43:09.193Z
---
DEFER until a native provider. Session identity is set once per opened root (src/metabrowser/inventory_engine/coordinator.py:607). If the provider's change stream fails or ends (coordinator.py:697-698), the relay logs, publishes one reset, and nothing restarts it (coordinator.py:663-671, :765-777); open() on the same root returns the current version without reopening (coordinator.py:315), and close() is terminal (coordinator.py:560). A crashed native engine would stop live updates for that root until the server restarts. Needs a reopen or supervise path, or the contract must state that provider restart is expressed as reset under an adapter-owned session.

## Notes

Confirmed during final stack review. This remains an explicit native adoption gate: either the adapter owns recovery under a stable opened session with reset, or the application supervises a reopen. Python remains the only shipped provider. Do not ship a crash-prone native process without a tested recovery policy. See the 2026-09-07 review.
