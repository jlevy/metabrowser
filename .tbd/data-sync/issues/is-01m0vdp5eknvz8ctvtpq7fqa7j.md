---
type: is
id: is-01m0vdp5eknvz8ctvtpq7fqa7j
title: "PR #74 review R5: clear projection caches on broad invalidation"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0vcsh5mt08cfhzztanzt880
created_at: 2026-08-25T02:58:42.771Z
updated_at: 2026-08-25T02:58:42.771Z
---
PR #74 review https://github.com/jlevy/metabrowser/pull/74#issuecomment-5404472008 at head 68eeaac. R5 Medium. runtime.py:69-74 handles only dirty_paths, so reset and all_dirty fact changes do not clear host projection caches. Add a public clear-all operation and test broad invalidation.
