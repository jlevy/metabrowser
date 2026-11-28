---
type: is
id: is-01m8cst8y0jqwef2tg9smftat0
title: Show SoftSchema tables on cached Git repository folders
kind: feature
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
hold: null
hold_until: null
created_at: 2026-11-26T20:47:38.424Z
updated_at: 2026-11-28T18:20:27.225Z
started_at: 2026-11-26T21:47:27.100Z
---
The current folder Table preview uses filesystem-only plugin hooks. On a cached Git pin, the original Universe repository opens People with Overview and Treemap but has no SoftSchema Table. Add source-aware candidate, schema, and record reads using the pinned repository inventory and object APIs. Scope projections by source and pin and verify the cached GitHub Universe People table opens with 577 records and linked details without unpacking a checkout.

## Notes

Phase 5 requires the additive upstream reader contract and one subject-bound directory handle shared by offer, collection index, table and record routes. A fresh cached-pin check confirmed unsupported_for_subject. An isolated local preview of the same revision showed 18 tables and opened its 41-row strategy table. This proves data discovery against the revision; the native cached-pin acceptance still requires the full integration.

Bounded Git reader and shared table projection checkpoint 6f4a515d64bfb9ede7b69daece5afb39d50646d3. Thirteen focused tests passed against the local upstream SoftSchema reader source, including an actual bare Git store, Unicode source wire identities, sibling schema, cross-folder backlink, a missing blob on a second commit, captured lease invalidation and no unchanged-payload rereads. Existing filesystem table and Git scaling routes remain green. The production dependency lock remains unchanged; pinned folder offer and route dispatch are in progress.
