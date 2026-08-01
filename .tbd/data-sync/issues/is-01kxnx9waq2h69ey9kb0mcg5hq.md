---
type: is
id: is-01kxnx9waq2h69ey9kb0mcg5hq
title: Quick file finder and search providers
kind: feature
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels:
  - search
  - scalability
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
child_order_hints:
  - is-01kyxyb67v18br7jm7w8mrwss5
  - is-01kyxybpctnfvcbj8eh629hab0
  - is-01kyxybvqnw3fmmzhs3hnqhtxr
created_at: 2026-07-16T16:49:05.366Z
updated_at: 2026-08-01T05:57:16.148Z
---
Build a provider-based search surface in phases. Phase 1 opens a slash-key quick file finder and fuzzy-matches a minimal catalog of every file already observed by the browser, without a search request. Phase 2 adds complete server filename fallback over InventoryIndex. Phase 3 adds explicit bounded server full-text search with location-aware results. Quick file and content queries stay separate from persisted FilterState and from hierarchical hide-mode filtering.

## Notes

2026-07-31 architecture and editor-pattern review replaced the filtered-tree search model. A DOM-independent controller owns provider selection, cancellation, result metadata, and fallback; the slash palette and a future persistent nav search are separate consumers. Local results disclose partial coverage, complete filename search can follow a zero-result local query, and full text is an explicit retrieval mode. Flat filename, path-and-location content, and hierarchical filter results use separate endpoints.
