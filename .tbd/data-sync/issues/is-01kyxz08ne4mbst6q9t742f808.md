---
type: is
id: is-01kyxz08ne4mbst6q9t742f808
title: "Spike 6: integrate catalog observation and file navigation"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies:
  - type: blocks
    target: is-01kyxz0fjsxaww2zkypg8wy78m
parent_id: is-01kyxyb67v18br7jm7w8mrwss5
created_at: 2026-08-01T06:08:24.749Z
updated_at: 2026-08-01T07:30:16.834Z
closed_at: 2026-08-01T07:30:16.833Z
close_reason: Integrated the quick-file assets into the browser shell, fed the catalog from initial tree, lazy tree, Recent, event snapshot/change, resync, and successful navigation seams, and returned explicit navigation outcomes with authoritative revalidation and focus transfer. Added structural integration coverage; make verify passes with 779 tests.
---
Wire the catalog to every browser observation seam and inject the finder into the existing application navigation path. Make navigateToPath and selection return explicit success, not-found, and retryable-failure outcomes. Verify that an unmounted lazy-tree file opens, a stale not-found candidate is removed without clearing the query, other failures stay visible and retryable, and successful opening moves focus to the destination. Preserve existing routes, filters, Recent, tree expansion, and public window.metabrowser behavior.
