---
type: is
id: is-01m0r8xt95921dabcddjjm7csf
title: Implement and evaluate the fdu inventory provider
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-08-23T21:37:47.300Z
updated_at: 2026-08-23T21:37:47.300Z
---
Phase 2 of the inventory-provider implementation plan. Prove the real PyO3 seam, implement the fdu Rust library behind the same InventoryHandle contract without mirror state, run the shared parity and reliability suites, measure Python versus fdu at the engine/server/browser layers, and add automatic selection only if the adoption gates pass.
