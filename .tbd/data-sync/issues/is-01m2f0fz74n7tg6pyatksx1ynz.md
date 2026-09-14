---
type: is
id: is-01m2f0fz74n7tg6pyatksx1ynz
title: "PR #114 review R5: search reports 'Scanning continues.' for a final truncated catalog"
kind: bug
status: open
priority: 3
version: 1
labels:
  - search
dependencies: []
parent_id: is-01m2f0fb55v9h6480r6cfx514k
created_at: 2026-09-14T03:48:38.755Z
updated_at: 2026-09-14T03:48:38.755Z
---
PR #114 review R5 (Low). src/metabrowser/static/search-palette.js:311-314, src/metabrowser/static/search-controller.js:280-286. When fileCatalog snapshot is truncated, the status text should say indexing stopped at the file limit, keeping the server fallback. PR #113 concurrently edits search-palette.js; keep the change local.
