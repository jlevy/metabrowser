---
type: is
id: is-01m0c4cxzv2gzbbxp15796r65j
title: "diff/service.py: resolution, self-describing IDs, bounded caches"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4cycfke1sadh3hd8a24wk
  - type: blocks
    target: is-01m0c4dg0mn2a39exqkjdvf6jv
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:46.535Z
updated_at: 2026-08-19T04:28:18.576Z
---
ComparisonService with register_adapter(name, source), create(intent), manifest(id), file_patch(id, file_id), content(id, file_id, side). comparison_id_for(resolved) derives the self-describing identifier so any GET can rebuild an evicted comparison rather than fail, and creation is idempotent. Bounded LRUs for manifests and patches; generation_token(resolved) backs the stale check for volatile comparisons.
