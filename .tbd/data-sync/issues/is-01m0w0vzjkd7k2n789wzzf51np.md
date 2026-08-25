---
type: is
id: is-01m0w0vzjkd7k2n789wzzf51np
title: "PR #74 scope audit S8: avoid repeated full projection work across tree pages"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:33:56.306Z
updated_at: 2026-08-25T08:33:56.306Z
---
assemble_tree_pages issues repeated version-pinned reads, while the Python provider rebuilds the complete directory or filtered-tree projection for every 4,096-row page. Large responses therefore repeat O(scope) copies, traversal, filtering, and aggregation once per page. Add a bounded one-version projection memo or another simple provider-local continuation implementation, measure/assert that later pages do not repeat full semantic work, and preserve FDU-neutral paging semantics.
