---
type: is
id: is-01kxnx9waq2h69ey9kb0mcg5hq
title: Build scalable file search over the live inventory
kind: feature
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels:
  - search
  - scalability
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:05.366Z
updated_at: 2026-08-01T05:13:10.201Z
---
Current prerequisites include the bounded eager inventory, lazy tree, index status endpoints, live filesystem events, and unified client filter state. Remaining delivery: canonical logical-extension identity for compressed artifacts; a public inventory revision and scope-safe revision event; a bounded off-event-loop search service and /api/search response with ancestors and honest inventory/result truncation; keyboard-first search UI that preserves the mounted Files tree; live refresh and large-root budgets. Persistent metadata remains evidence-gated, not part of the initial contract.

## Notes

2026-07-31 spec review reconciled this feature with the current browser and unified-filtering Phase 1. Stable path order, empty-keyword hide mode, revision-only invalidation, client abort/stale-response handling, and a separate search result panel are now resolved decisions. Open questions are shortcut choice, measured limits/debounce, type-family expansion ownership, cooperative server cancellation, and evidence for persistence.
