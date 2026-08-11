---
type: is
id: is-01kyxybpctnfvcbj8eh629hab0
title: "P2: add complete server filename search provider"
kind: task
status: deferred
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxybvqnw3fmmzhs3hnqhtxr
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:57:10.681Z
updated_at: 2026-08-09T18:03:26.527Z
---
DEFERRED — premise superseded by the mb-ci04 decision (2026-08-06): Quick File is client-complete over non-gitignored filenames via a minimal bulk feed (mb-hj78); no per-query server filename search on the default path, and 'do not transfer the full inventory' no longer governs (it was sized against unfiltered inventories that are ~98% gitignored junk).

Retained as the fallback for roots whose NON-IGNORED file count makes client-complete unreasonable (multi-hundred-k monorepos, or past the 500k inventory cap). If built, the original scope stands: bounded flat /api/search/files over a consistent InventoryIndex snapshot, Python/JavaScript fuzzy-score parity fixtures, truncation metadata, cancellation. Blocked on evidence that such roots are a real use case.

## Notes

Phase 1 exposes fallback provider activation and an explicit includeFallback search option. Phase 2 must add the indexed filename provider plus coalesced catalog and inventory revision subscriptions so an open query refreshes when coverage changes. Before explicit complete search ships, define a shared cross-runtime rank or authoritative complete-batch replacement, and define coverage dominance so a complete server batch is not misranked or reported incomplete because an earlier local batch was partial. Phase 1 otherwise refreshes on the next input change or palette reopen.
