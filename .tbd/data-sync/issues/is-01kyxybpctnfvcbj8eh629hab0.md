---
type: is
id: is-01kyxybpctnfvcbj8eh629hab0
title: "P2: add complete server filename search provider"
kind: task
status: deferred
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:57:10.681Z
updated_at: 2026-11-14T18:42:34.245Z
extensions:
  linear:
    id: 9ec87dfa-bdb5-4285-94a6-3f1d4e7b62d9
    linked_at: 2026-08-16T08:06:42.091Z
---
DEFERRED. Premise superseded by the mb-ci04 decision (2026-08-06): Quick Search is client-complete over non-gitignored filenames through a minimal bulk feed (mb-hj78), so there is no per-query server filename search on the default path.

Retained as the fallback for roots whose non-ignored file count makes client-complete unreasonable (multi-hundred-thousand-file monorepos, or past the 500,000-file inventory cap). If built, the original scope stands: a bounded flat /api/search/files over a consistent inventory provider snapshot, Python and JavaScript fuzzy-score parity fixtures, truncation metadata, and cancellation. Blocked on evidence that such roots are a real use case.

## Notes

Phase 1 exposes fallback provider activation and an explicit includeFallback search option. Phase 2 must add the indexed filename provider plus coalesced catalog and inventory revision subscriptions so an open query refreshes when coverage changes. Before explicit complete search ships, define a shared cross-runtime rank or authoritative complete-batch replacement, and define coverage dominance so a complete server batch is not misranked or reported incomplete because an earlier local batch was partial. Phase 1 otherwise refreshes on the next input change or palette reopen.
