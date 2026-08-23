---
type: is
id: is-01m0r8xj4bv4bbrr65vw28d31j
title: Extract and ship the Python inventory reference provider
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0r8xt95921dabcddjjm7csf
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
child_order_hints:
  - is-01m0qyzmmmym17nxw6m7964xcp
created_at: 2026-08-23T21:37:38.952Z
updated_at: 2026-08-23T21:37:57.788Z
---
Phase 1 of the inventory-provider implementation plan. Preserve current Metabrowser behavior while moving every inventory consumer behind the sealed coordinator and Python provider, fixing coherent read/version capture, extracting sparse overlays, deleting the singleton seam, and recording the provider-aware performance baseline. This phase has no fdu dependency.
