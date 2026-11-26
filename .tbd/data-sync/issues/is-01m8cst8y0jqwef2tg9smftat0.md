---
type: is
id: is-01m8cst8y0jqwef2tg9smftat0
title: Show SoftSchema tables on cached Git repository folders
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
hold: null
hold_until: null
created_at: 2026-11-26T20:47:38.424Z
updated_at: 2026-11-26T21:47:44.340Z
started_at: 2026-11-26T21:47:27.100Z
---
The current folder Table preview uses filesystem-only plugin hooks. On a cached Git pin, the original Universe repository opens People with Overview and Treemap but has no SoftSchema Table. Add source-aware candidate, schema, and record reads using the pinned repository inventory and object APIs. Scope projections by source and pin and verify the cached GitHub Universe People table opens with 577 records and linked details without unpacking a checkout.

## Notes

Phase 5 now describes the bounded pinned-tree reader, shared folder offer and table source, immutable index key, encoded Git links and Universe acceptance. The current cached Git view still offers Overview and Treemap.
