---
type: is
id: is-01m8cst8y0jqwef2tg9smftat0
title: Show SoftSchema tables on cached Git repository folders
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
created_at: 2026-11-26T20:47:38.424Z
updated_at: 2026-11-26T20:47:38.424Z
---
The current folder Table preview uses filesystem-only plugin hooks. On a cached Git pin, the original Universe repository opens People with Overview and Treemap but has no SoftSchema Table. Add source-aware candidate, schema, and record reads using the pinned repository inventory and object APIs. Scope projections by source and pin and verify the cached GitHub Universe People table opens with 577 records and linked details without unpacking a checkout.
