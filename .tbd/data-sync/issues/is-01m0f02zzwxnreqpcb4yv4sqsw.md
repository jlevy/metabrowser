---
type: is
id: is-01m0f02zzwxnreqpcb4yv4sqsw
title: "PR #58 review R2: comparison_handler misses DiffSourceError -> unknown revision 500s; ValueError arm dead"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:09.915Z
updated_at: 2026-08-20T07:10:09.915Z
---
PR #58, review 4979975854, finding R2. comparison_handler misses DiffSourceError -> unknown revision 500s; ValueError arm dead. sidekick.py:212-215; catch DiffSourceError -> 404
