---
type: is
id: is-01m0f0314ftcbrx7m1bhnwgdd0
title: "PR #58 review R6: Apply oracle order-dependent; added-over-existing overwrites; ready delete w/o patch skips verification"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.086Z
updated_at: 2026-08-20T07:35:57.029Z
closed_at: 2026-08-20T07:35:57.028Z
close_reason: "R6 fixed in c0ae341: two-phase apply, added-over-existing and duplicate-produce refuse, ready delete without patch is NotFullyHydrated; apply-order-independent corpus case"
---
PR #58, review 4979975854, finding R6. Apply oracle order-dependent; added-over-existing overwrites; ready delete w/o patch skips verification. apply.py:171-221; two-phase apply + ApplyError + NotFullyHydrated
