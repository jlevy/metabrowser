---
type: is
id: is-01m01gfgdgh9nx8c8ymvq3hgfq
title: Add semantic tooltips to folder composition bars
kind: feature
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-15T01:27:15.119Z
updated_at: 2026-08-15T01:42:54.615Z
closed_at: 2026-08-15T01:42:54.614Z
close_reason: Implemented semantic family tooltips, group-first active-metric ordering, shared control scope, lifecycle cleanup, tests, and design documentation.
---
Add accessible hover and keyboard-focus tooltips to each semantic segment in the Files and Ignored composition bars. Reuse a shared tooltip primitive or generalize the existing design-system vocabulary; show the segment color, semantic type name, exact file count, and formatted byte size for the row's disjoint population in either selected metric. Keep bars decorative in reading order, preserve full-track hit areas for tiny segments where feasible, avoid duplicate rollup work, cover lifecycle/positioning/responsive behavior with TDD, and update design documentation.
