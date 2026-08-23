---
type: is
id: is-01m0rbqr7asmz6pt6vbejmzdj1
title: Migrate recent, catalog, metadata, capability and folder queries
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
dependencies:
  - type: blocks
    target: is-01m0rbqsb3e5ep9c328y6ybk4z
parent_id: is-01m0r8xj4bv4bbrr65vw28d31j
created_at: 2026-08-23T22:26:54.313Z
updated_at: 2026-08-23T22:26:55.458Z
---
Files: refactor src/metabrowser/recent.py, activity.py, events_route.py and server.py api_recent, api_catalog, api_index_progress, api_index_meta, api_capabilities, _api_folder_envelope and api_activity; update their route and wire tests. Functions: make recent projection pure over a coherent entry snapshot; page CatalogQuery behind the coordinator without mixing versions; derive catalog validators from ReadResult; source folder facts, progress, metadata, suffixes and diagnostics from typed projections; include provider and contract identity in diagnostics/capabilities. Remove inventory-serving filesystem truth paths, except any measured cold fallback contained inside the Python provider with explicit source/coverage. Acceptance: current response shapes, gzip, ETags, recency cap policy, catalog convergence, diagnostics and folder plugin behavior are preserved.
