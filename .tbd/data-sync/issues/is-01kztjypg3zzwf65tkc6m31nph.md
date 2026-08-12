---
type: is
id: is-01kztjypg3zzwf65tkc6m31nph
title: Keep the root summary pending until its inventory snapshot is complete
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-12T08:55:48.991Z
updated_at: 2026-08-12T09:04:54.406Z
closed_at: 2026-08-12T09:04:54.406Z
close_reason: Implemented with regression coverage; full make verify passed on 2026-08-12.
---
loadTree nulls fallback totals while tally_cache_status is scanning but still passes data.summary into treeSummaryHtml, which wins and renders a concrete partial tracked/ignored tally. Gate the authoritative summary itself on scan completion and strengthen the structural regression test.

## Notes

loadTree now withholds data.summary while tally_cache_status is scanning, keeping tracked and ignored totals pending until the corresponding inventory snapshot is complete. Structural regression coverage was strengthened. Full make verify passed on 2026-08-12.
