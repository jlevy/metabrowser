---
type: is
id: is-01kzwkvtqqrtdyafd6vkspsm9b
title: Extract and extend the inventory rollup
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - backend
dependencies:
  - type: blocks
    target: is-01kzwkxst27f1wrrq2ktft2jmy
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:12.470Z
updated_at: 2026-08-13T06:16:35.799Z
closed_at: 2026-08-13T06:16:35.799Z
close_reason: Implemented and validated on codex/folder-overview-implementation; focused coverage and make verify pass.
---
Implement the Server and Inventory Function Map for inventory_rollup.py, inventory.py, settings.py, wire_models.py, and api_rollup. Make InventoryIndex.rollup a thin delegate; support depth/top zero and opt-in ext_rank=dual; preserve byte default; calculate exact all/unignored named and Other tallies from the union of counters; validate the wire contract. Tests must cover count-heavy versus byte-heavy ranking, ignored-only, extensionless, compound, zero-byte, cold/scanning/truncated, node/payload bounds, and the 100k-entry performance target.
