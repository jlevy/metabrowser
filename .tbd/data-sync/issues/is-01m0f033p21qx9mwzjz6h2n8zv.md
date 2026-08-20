---
type: is
id: is-01m0f033p21qx9mwzjz6h2n8zv
title: "PR #58 review R15: --diff --format yaml silently prints text"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:13.698Z
updated_at: 2026-08-20T07:35:59.302Z
closed_at: 2026-08-20T07:35:59.301Z
close_reason: "R15 fixed in c0ae341: --format yaml refused with a clear message; golden pins the refusal"
---
PR #58, review 4979975854, finding R15. --diff --format yaml silently prints text. diff_cli.py:238; reject yaml with a clear message + golden
