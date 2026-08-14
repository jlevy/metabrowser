---
type: is
id: is-01kzyh1b0w39cneqhcc0q68hw3
title: "PR #37 review F5: Clarify Treemap header sizing contract"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:16.124Z
updated_at: 2026-08-13T21:53:02.228Z
closed_at: 2026-08-13T21:53:02.227Z
close_reason: "Fixed: headerPx is no longer advertised as a layout override; the label strip is documented and tested as typography-derived."
---
F5 Low at src/metabrowser/builtin_plugins/folder/treemap_layout.js:18. headerPx is described as caller-overridable but cellTypography reads the constant directly. Choose and test one coherent contract; prefer removing it from general layout options if the header is derived from typography.
