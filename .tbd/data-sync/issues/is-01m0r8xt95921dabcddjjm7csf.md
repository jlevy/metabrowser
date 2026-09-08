---
type: is
id: is-01m0r8xt95921dabcddjjm7csf
title: Implement and evaluate the fdu inventory provider
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
child_order_hints:
  - is-01m0tc6jhy1c64c4z6m3z2xxtq
  - is-01m0tgwqjj6w5awgwbgqtk1mqe
  - is-01m0txhaybmj82ym2wcm85zz0b
  - is-01m0tytbmjsb46bnmh5134r5tg
created_at: 2026-08-23T21:37:47.300Z
updated_at: 2026-09-08T00:00:24.670Z
---
Phase 2 of the inventory-provider implementation plan. Prove the real PyO3 seam, implement the fdu Rust library behind the same InventoryHandle contract without mirror state, run the shared parity and reliability suites, measure Python versus fdu at the engine/server/browser layers, and add automatic selection only if the adoption gates pass.

## Notes

Final PR101 review establishes native adoption gates: native aggregate projections without rebuilding a Python inventory graph, recovery/session policy (mb-6o0l), useful pinned-page completion and explicit eviction under churn (contract now states semantics; current Python behavior fixed in mb-6elt), text/stream walk semantics (mb-iyu7), and measured binding/readback costs (mb-l2eh). The Python stack can merge separately after full verification.
