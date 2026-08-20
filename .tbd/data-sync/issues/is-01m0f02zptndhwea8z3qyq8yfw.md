---
type: is
id: is-01m0f02zptndhwea8z3qyq8yfw
title: "PR #58 review R1: parse_unified_patch not total: six crash inputs (unguarded int() on similarity/octal, negative hunk starts, rename w/o similarity)"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:09.625Z
updated_at: 2026-08-20T07:35:55.763Z
closed_at: 2026-08-20T07:35:55.763Z
close_reason: "R1 fixed in c0ae341: guards at all six sites plus the structural degrade net; six probes pinned as tests"
---
PR #58, review 4979975854, finding R1. parse_unified_patch not total: six crash inputs (unguarded int() on similarity/octal, negative hunk starts, rename w/o similarity). Guard sites + structural degrade net at final validation. patch_file.py:83,170,237,455
