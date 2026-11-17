---
type: is
id: is-01m7m17dpsrh1qmdx50e08xkzn
title: Map moved-version errors to a typed retryable answer in every assembly consumer (R31)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T05:56:08.536Z
updated_at: 2026-11-17T05:56:08.536Z
---
Tree, catalog, the SSE snapshot, and the --walk and --api paths let an unpinned VersionUnavailableError escape (server.py, events_route.py, walk.py); only the rollup route handles the pinned case. One mapping (503 with a retry hint), one golden. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R31.
