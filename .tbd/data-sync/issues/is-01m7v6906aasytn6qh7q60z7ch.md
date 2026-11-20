---
type: is
id: is-01m7v6906aasytn6qh7q60z7ch
title: "PR #617 A9: cell and key encoding not total over SQLite values"
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
created_at: 2026-11-20T00:39:04.138Z
updated_at: 2026-11-20T00:58:47.033Z
started_at: 2026-11-20T00:39:18.360Z
closed_at: 2026-11-20T00:58:47.033Z
close_reason: 'fixed in `d5ea44d`: `{int: "<decimal>"}` outside ±(2^53−1), `{real: "inf"}` etc., text read as bytes and decoded with replacement marked `invalid_utf8`, opaque server-minted `key`, `ref` names field lists, a null-cursor branch for keyset predicates, and each case in the golden fixtures. Confirmed in `fda5f4c` (results/encoding.json): with the null branch, row-value paging matches one `ORDER BY` over mixed types under every affinity and `NOCASE`, keeping the index seek'
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 238-266, 359-364. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A9).
