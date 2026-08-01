---
type: is
id: is-01kyxybpctnfvcbj8eh629hab0
title: "P2: add complete server filename search provider"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxybvqnw3fmmzhs3hnqhtxr
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:57:10.681Z
updated_at: 2026-08-01T08:22:55.151Z
---
Add a bounded flat /api/search/files provider over a consistent InventoryIndex snapshot, a public inventory revision, Python and JavaScript fuzzy-score parity fixtures, result and inventory truncation metadata, cancellation, automatic fallback only after zero incomplete local results, and an explicit search-all action. Do not transfer the full inventory or reuse the hierarchical filter projection.

## Notes

Phase 1 exposes fallback provider activation and an explicit includeFallback search option. Phase 2 must add the indexed filename provider plus coalesced catalog and inventory revision subscriptions so an open query refreshes when coverage changes. Before explicit complete search ships, define a shared cross-runtime rank or authoritative complete-batch replacement, and define coverage dominance so a complete server batch is not misranked or reported incomplete because an earlier local batch was partial. Phase 1 otherwise refreshes on the next input change or palette reopen.
