---
type: is
id: is-01m2f0fz74n7tg6pyatksx1ynz
title: "PR #114 review R5: search reports 'Scanning continues.' for a final truncated catalog"
kind: bug
status: closed
priority: 3
version: 2
labels:
  - search
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:38.755Z
updated_at: 2026-09-14T04:45:54.971Z
closed_at: 2026-09-14T04:45:54.970Z
close_reason: "Fixed in de282ce5: search palette idle line and local provider status say 'Indexing stopped at the file limit.' when snapshot.truncated; complete stays false so the server fallback still runs. DOM and provider assertions added."
resolution: null
duplicate_of: null
---
PR #114 review R5 (Low). src/metabrowser/static/search-palette.js:311-314, src/metabrowser/static/search-controller.js:280-286. When fileCatalog snapshot is truncated, the status text should say indexing stopped at the file limit, keeping the server fallback. PR #113 concurrently edits search-palette.js; keep the change local.
