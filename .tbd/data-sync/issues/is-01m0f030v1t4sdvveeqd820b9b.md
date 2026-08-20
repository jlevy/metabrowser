---
type: is
id: is-01m0f030v1t4sdvveeqd820b9b
title: "PR #58 review R5: Multi-file plain unified diffs collapse to one unsupported section: in_hunks never cleared by counts"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:10.784Z
updated_at: 2026-08-20T07:35:56.765Z
closed_at: 2026-08-20T07:35:56.764Z
close_reason: "R5 fixed in c0ae341: hunk-count budgets end sections; no-newline tail preserved; diff -ru golden-shaped test added"
---
PR #58, review 4979975854, finding R5. Multi-file plain unified diffs collapse to one unsupported section: in_hunks never cleared by counts. patch_file.py:151-157
