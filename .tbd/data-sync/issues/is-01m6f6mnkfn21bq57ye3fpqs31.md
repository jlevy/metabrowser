---
type: is
id: is-01m6f6mnkfn21bq57ye3fpqs31
title: Any PR that deletes an empty file has no Files changed
kind: bug
status: open
priority: 0
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3ne8f25m4n06r3d09zw9d
created_at: 2026-11-02T22:38:51.502Z
updated_at: 2026-11-02T22:38:51.502Z
---
parse_unified_patch cannot model a deleted empty file, returns an empty document when any section fails, and the route answers 404 file f1 not found. Found by exp-040 on a 663-file PR and a public 301-file one; on main too, and shared with .patch files on plain folders. First commit on claude/v012-large-pr-perf.
