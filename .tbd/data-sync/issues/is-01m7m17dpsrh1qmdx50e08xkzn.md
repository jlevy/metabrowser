---
type: is
id: is-01m7m17dpsrh1qmdx50e08xkzn
title: Map moved-version errors to a typed retryable answer in every assembly consumer (R31)
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
hold: null
hold_until: null
created_at: 2026-11-17T05:56:08.536Z
updated_at: 2026-11-17T17:17:40.350Z
started_at: 2026-11-17T08:09:57.158Z
---
Tree, catalog, the SSE snapshot, and the --walk and --api paths let an unpinned VersionUnavailableError escape (server.py, events_route.py, walk.py); only the rollup route handles the pinned case. One mapping (503 with a retry hint), one golden. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, R31.

## Notes

Implemented in layer 3c, jlevy/metabrowser#520: inventory_moved.py 503 + Retry-After, SSE resync, --walk CLIError; ProviderFailureError mapped too.
