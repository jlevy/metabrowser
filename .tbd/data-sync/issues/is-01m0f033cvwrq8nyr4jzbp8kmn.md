---
type: is
id: is-01m0f033cvwrq8nyr4jzbp8kmn
title: "PR #58 review R14: Hardcoded SHA-1 empty-tree oid breaks root-commit diffs in sha256 repos"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:13.402Z
updated_at: 2026-08-20T07:35:59.039Z
closed_at: 2026-08-20T07:35:59.039Z
close_reason: "R14 fixed in c0ae341: empty-tree oid derived per repo via git hash-object -t tree /dev/null"
---
PR #58, review 4979975854, finding R14. Hardcoded SHA-1 empty-tree oid breaks root-commit diffs in sha256 repos. git.py:156; derive per source
