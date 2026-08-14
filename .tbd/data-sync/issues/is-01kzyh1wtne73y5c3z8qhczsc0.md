---
type: is
id: is-01kzyh1wtne73y5c3z8qhczsc0
title: "PR #37 review S1: Reuse extension-key union helper"
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:34.356Z
updated_at: 2026-08-13T21:53:02.661Z
closed_at: 2026-08-13T21:53:02.660Z
close_reason: "Applied: factored _all_extension_keys for selection and remainder serialization."
---
Suggestion S1 at src/metabrowser/inventory_rollup.py:305 and 343. Avoid recomputing the same four-way extension-key union by factoring one helper or returning the already-computed union.
