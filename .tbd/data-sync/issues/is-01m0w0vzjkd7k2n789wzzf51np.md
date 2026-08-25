---
type: is
id: is-01m0w0vzjkd7k2n789wzzf51np
title: "PR #74 scope audit S8: avoid repeated full projection work across tree pages"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:33:56.306Z
updated_at: 2026-08-25T09:57:01.009Z
closed_at: 2026-08-25T09:57:01.009Z
close_reason: "Completed in 0577bb125c4a607719befa3f213362f5522d5724. Exact-head make format, make lint-check, two make verify runs, pre-commit, pre-push, and all five GitHub checks pass. Full issue-comment, formal-review, inline-comment, and review-thread sweep is clean. Per-finding disposition: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5408540376"
resolution: null
duplicate_of: null
---
assemble_tree_pages issues repeated version-pinned reads, while the Python provider rebuilds the complete directory or filtered-tree projection for every 4,096-row page. Large responses therefore repeat O(scope) copies, traversal, filtering, and aggregation once per page. Add a bounded one-version projection memo or another simple provider-local continuation implementation, measure/assert that later pages do not repeat full semantic work, and preserve FDU-neutral paging semantics.
