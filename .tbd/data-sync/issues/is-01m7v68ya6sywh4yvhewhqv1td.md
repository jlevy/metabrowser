---
type: is
id: is-01m7v68ya6sywh4yvhewhqv1td
title: "PR #617 A5: substr and length load the whole value; preview claim false"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:02.214Z
updated_at: 2026-11-20T00:58:45.712Z
started_at: 2026-11-20T00:39:16.960Z
closed_at: 2026-11-20T00:58:45.712Z
close_reason: "fixed in `d5ea44d`: sizes from `octet_length` and `typeof`; previews past a measured threshold through `blobopen`; size-only cells for `WITHOUT ROWID` tables and views; `SQLITE_LIMIT_LENGTH` as a backstop mapped to a per-cell `{error}`; same rule for the record route. Confirmed in `fda5f4c` (results/values.json: `substr`/`length` on 200 MiB text peak 219 MiB; `octet_length` and `blobopen` 18 MiB)"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 227, 249-250, 351-352. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A5).
