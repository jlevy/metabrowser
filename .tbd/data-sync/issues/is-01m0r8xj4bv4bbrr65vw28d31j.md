---
type: is
id: is-01m0r8xj4bv4bbrr65vw28d31j
title: Extract and ship the Python inventory reference provider
kind: epic
status: closed
priority: 1
version: 20
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0r8xt95921dabcddjjm7csf
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
child_order_hints:
  - is-01m0rbnz3hc49nr34acsthfdj2
  - is-01m0rbqpga27g7sz5v7rs29mbf
  - is-01m0rbqpvchne5gpw8bsmzt5bq
  - is-01m0rbqq5z7qns1c2jy5pqrk5b
  - is-01m0rbqqh02gf2hnbz1mzbn617
  - is-01m0qyzmmmym17nxw6m7964xcp
  - is-01m0rbqqw9a3dv398mhqhzw93h
  - is-01m0rbqr7asmz6pt6vbejmzdj1
  - is-01m0rbqrnt4bw8zs3d1acdwbbx
  - is-01m0rbqs0ad7a2gnpg79fp1jk7
  - is-01m0rbqsb3e5ep9c328y6ybk4z
  - is-01m0rbqspkv8et5wzmchk9c5mv
  - is-01m0rbqt1448pdt09sadn5xdpa
  - is-01m0rbqtbt3mjghbxhcryzjewp
created_at: 2026-08-23T21:37:38.952Z
updated_at: 2026-08-24T03:12:25.445Z
closed_at: 2026-08-24T03:12:25.444Z
close_reason: Phase 1 is complete. MetaBrowser now ships the behavior-preserving Python reference provider behind the sealed InventoryBackend and InventoryHandle contract, one coordinator and sparse overlay own application state, every production consumer is migrated, the singleton is deleted, provider-aware performance evidence is integrated, make verify and GitHub CI pass, and no fdu dependency is present.
resolution: null
duplicate_of: null
---
Phase 1 implementation epic for the inventory-provider plan. Preserve every observable MetaBrowser behavior while replacing the process-wide InventoryIndex ownership seam with a sealed InventoryBackend and InventoryHandle contract, one Python reference provider, an application-owned InventoryCoordinator, coherent versioned reads, bounded change delivery, a sparse host overlay, provider-aware performance evidence, and no fdu dependency. All production consumers must migrate and the obsolete singleton/direct-provider paths must be deleted before this epic closes.
