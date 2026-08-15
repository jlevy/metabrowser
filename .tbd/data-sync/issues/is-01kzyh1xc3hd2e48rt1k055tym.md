---
type: is
id: is-01kzyh1xc3hd2e48rt1k055tym
title: "PR #37 review S3: Preserve remainder byte magnitudes"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:34.914Z
updated_at: 2026-08-13T21:53:03.093Z
closed_at: 2026-08-13T21:53:03.092Z
close_reason: "Applied: remainder aggregation now preserves true byte magnitudes in both size and file metric modes, including client-side folds."
---
Suggestion S3 at src/metabrowser/builtin_plugins/folder/treemap_layout.js:416. Rest cells should carry the true byte magnitude in both metric modes, consistent with the model invariant and sibling cells.
