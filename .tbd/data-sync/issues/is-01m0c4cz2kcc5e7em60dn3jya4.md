---
type: is
id: is-01m0c4cz2kcc5e7em60dn3jya4
title: "static/diff_view.js: unified renderer with every availability state"
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0c4czd01fxz2rv1na9s3b5q
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
created_at: 2026-08-19T04:27:47.666Z
updated_at: 2026-08-19T16:19:41.875Z
closed_at: 2026-08-19T16:19:41.874Z
close_reason: "Landed as builtin_plugins/diff/diff_view.js: unified hunks, indicator set, every availability state labeled, dispose tested. Same plugin-local placement note as mb-snkb."
---
mountDiffView(container, patch, options) -> { dispose } with renderHunk, renderLine, expandContext(hunk, direction), renderAvailability(state) so every non-content state has exactly one rendering path. Sticky file headers. Disposal releases observers and any workers, as every mounted view must.
