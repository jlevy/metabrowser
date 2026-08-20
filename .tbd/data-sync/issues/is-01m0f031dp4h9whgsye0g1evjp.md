---
type: is
id: is-01m0f031dp4h9whgsye0g1evjp
title: "PR #58 review R7: CLI A"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0f02zaw865q3swdc9xvmdb9
created_at: 2026-08-20T07:10:11.381Z
updated_at: 2026-08-20T07:10:11.381Z
---
PR #58, review 4979975854, finding R7. CLI A...B silently treated as A..B (direct instead of merge-base). diff_cli.py:67-69; parse three-dot -> base_policy merge_base + divergent-branch golden
