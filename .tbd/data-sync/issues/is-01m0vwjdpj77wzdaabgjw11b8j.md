---
type: is
id: is-01m0vwjdpj77wzdaabgjw11b8j
title: "PR #74 review 74-5: bound aggregate ReadRequest work"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0vwgx7e4bgwvkjbdsaejjtz
created_at: 2026-08-25T07:18:48.778Z
updated_at: 2026-08-25T07:58:58.703Z
closed_at: 2026-08-25T07:58:58.702Z
close_reason: "Fixed: ReadRequest enforces MAX_QUERIES_PER_READ across the aggregate query bundle."
resolution: null
duplicate_of: null
---
Review 5406736360. ReadRequest has per-query bounds but no total query bound; one dirty batch can create 1024 EntryQuery values. Add a defensible aggregate limit or chunk _project_change, document and test the selected bound.
