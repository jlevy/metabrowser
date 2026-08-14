---
type: is
id: is-01kzyh1a8cgebbdzj1r8vx5xqx
title: "PR #37 review F2: Restore endpoint timing decorators"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - pr-review
  - pr-37
dependencies: []
parent_id: is-01kzyh19dnb273gz5mhw90bse3
created_at: 2026-08-13T21:39:15.339Z
updated_at: 2026-08-13T21:53:01.547Z
closed_at: 2026-08-13T21:53:01.546Z
close_reason: "Fixed: timing decorators are restored on api_tree and api_file, added to api_rollup, and removed from the inserted helpers; regression coverage pins handler decoration."
---
F2 Medium at src/metabrowser/server.py:1022, 1147, and 1382. Helpers accidentally captured decorators intended for api_tree and api_file; api_rollup has none. Restore handler instrumentation and avoid tracing lightweight helpers unintentionally.
