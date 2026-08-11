---
type: is
id: is-01kzfesrv946304npftpks4c1b
title: Exclude gitignored files from the Quick File catalog (hardcoded global)
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-08T01:11:34.504Z
updated_at: 2026-08-09T17:43:02.383Z
closed_at: 2026-08-09T17:43:02.383Z
close_reason: "Shipped in 16678d3. inventory.catalog_files() returns only non-gitignored files and _derive_catalog_change() converts a gitignored upsert into a removal, so the exclusion holds for the bulk fetch and for live deltas. Verified on the running server: /api/catalog returns 273 files with zero entries under node_modules, .venv, or attic. mb-nri5 and mb-2h3i were duplicates of the same request."
---
Search results must not include gitignored files — node_modules and the like pollute every query. Global setting, hardcoded on for now.

- Server: the mb-hj78 bulk feed and its delta path filter on the existing FsEntry.gitignored flag. One named constant (future config surface; the treemap's gitignored toggle vocabulary is where a real setting eventually lands).
- Client: known_file_catalog rejects gitignored entries at every opportunistic seam. Verified flag availability: /api/tree nodes and /api/recent entries_flat carry gitignored; SSE FsEntry carries it; /api/file responses DO NOT — either add the field there or accept that observeNavigation cannot filter (a gitignored file the user explicitly opened entering the catalog is minor; decide at implementation).
- Navigation is unaffected: the tree still shows and opens gitignored files (dimmed), Recent keeps its own handling. This exclusion is the search catalog only.
- Measured effect on this repo: 12,565 inventory files -> 270 in the catalog.
