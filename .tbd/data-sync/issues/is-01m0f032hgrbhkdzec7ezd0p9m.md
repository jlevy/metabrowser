---
type: is
id: is-01m0f032hgrbhkdzec7ezd0p9m
title: "PR #58 review R11: _narrow_to_path marks binary-only selection estimated; binary counts as exact zeros"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:12.527Z
updated_at: 2026-08-20T07:35:58.278Z
closed_at: 2026-08-20T07:35:58.277Z
close_reason: "R11 fixed in c0ae341: binary changes count as exact zeros in narrowed totals"
---
PR #58, review 4979975854, finding R11. _narrow_to_path marks binary-only selection estimated; binary counts as exact zeros. sidekick.py:124-133
