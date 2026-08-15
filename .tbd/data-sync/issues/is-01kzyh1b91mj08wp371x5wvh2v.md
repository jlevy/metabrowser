---
type: is
id: is-01kzyh1b91mj08wp371x5wvh2v
title: "PR #37 review F6: Hoist rollup node-limit import"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:16.385Z
updated_at: 2026-08-13T21:53:02.442Z
closed_at: 2026-08-13T21:53:02.441Z
close_reason: "Fixed: ROLLUP_MAX_NODES is imported at module scope."
---
F6 Low at src/metabrowser/inventory.py:451. ROLLUP_MAX_NODES is a function-local import without a cycle. Hoist it to the module imports or document a real reason for deferral.
