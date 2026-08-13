---
type: is
id: is-01kzyh1xz7t640j6s7cgm3cxpp
title: "PR #37 review S5: Reclaim palette slots after extension churn"
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
created_at: 2026-08-13T21:39:35.526Z
updated_at: 2026-08-13T21:53:03.526Z
closed_at: 2026-08-13T21:53:03.525Z
close_reason: "Applied: palette sessions track each live consumer, prune removed assignments, rebuild reserved slots, and retain keys still used by another view."
---
Suggestion S5 at src/metabrowser/builtin_plugins/folder/category_palette.js:22. Rebuild reserved slots from live assignments during sync so removed extension keys do not consume slots forever and force avoidable fallback collisions.
