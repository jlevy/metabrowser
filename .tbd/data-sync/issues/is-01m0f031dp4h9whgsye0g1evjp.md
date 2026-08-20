---
type: is
id: is-01m0f031dp4h9whgsye0g1evjp
title: "PR #58 review R7: CLI A"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.381Z
updated_at: 2026-08-20T07:35:57.275Z
closed_at: 2026-08-20T07:35:57.274Z
close_reason: "R7 fixed in c0ae341: three-dot resolves merge base; tryscript golden with a divergent branch proves it"
---
PR #58, review 4979975854, finding R7. CLI A...B silently treated as A..B (direct instead of merge-base). diff_cli.py:67-69; parse three-dot -> base_policy merge_base + divergent-branch golden
