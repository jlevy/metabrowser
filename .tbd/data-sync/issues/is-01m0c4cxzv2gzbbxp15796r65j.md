---
type: is
id: is-01m0c4cxzv2gzbbxp15796r65j
title: "diff/service.py: resolution, self-describing IDs, bounded caches"
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4cycfke1sadh3hd8a24wk
  - type: blocks
    target: is-01m0c4dg0mn2a39exqkjdvf6jv
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:46.535Z
updated_at: 2026-08-20T17:24:04.327Z
---
ComparisonService with register_adapter(name, source), create(intent), manifest(id), file_patch(id, file_id), content(id, file_id, side). comparison_id_for(resolved) derives the self-describing identifier so any GET can rebuild an evicted comparison rather than fail, and creation is idempotent. Bounded LRUs for manifests and patches; generation_token(resolved) backs the stale check for volatile comparisons.

## Notes

User hit the deferred dead end live: a >50-file commit click shows 'not been loaded yet' with no loader. Landing the thin slice now: comparison hook gains ?file=<path> narrowing (hydrates just that change), and the diff view renders a Load control on deferred sections that fetches and splices the hunks. The full service (cross-request caching, generation tokens, /api/diff collection) remains this bead.
