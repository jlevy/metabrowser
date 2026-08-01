---
type: is
id: is-01kyxybpctnfvcbj8eh629hab0
title: "P2: add complete server filename search provider"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxybvqnw3fmmzhs3hnqhtxr
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:57:10.681Z
updated_at: 2026-08-01T05:57:16.148Z
---
Add a bounded flat /api/search/files provider over a consistent InventoryIndex snapshot, a public inventory revision, Python and JavaScript fuzzy-score parity fixtures, result and inventory truncation metadata, cancellation, automatic fallback only after zero incomplete local results, and an explicit search-all action. Do not transfer the full inventory or reuse the hierarchical filter projection.
