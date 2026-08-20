---
type: is
id: is-01m0f032twfqqhb35n03b2fxef
title: "PR #58 review R12: diff --git path guess ignores authoritative ---/+++ lines for ambiguous names"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:12.827Z
updated_at: 2026-08-20T07:35:58.528Z
closed_at: 2026-08-20T07:35:58.527Z
close_reason: "R12 fixed in c0ae341: authoritative ---/+++ paths override the diff --git guess via provenance flags; ambiguous-name test added"
---
PR #58, review 4979975854, finding R12. diff --git path guess ignores authoritative ---/+++ lines for ambiguous names. patch_file.py:139,186
