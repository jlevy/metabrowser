---
type: is
id: is-01m7v695ycgaq9wfdernw6n58t
title: "PR #617 A22: read columns with table_xinfo; mark STRICT; handle a column shadowing rowid"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:10.028Z
updated_at: 2026-11-20T00:58:51.351Z
started_at: 2026-11-20T00:39:22.836Z
closed_at: 2026-11-20T00:58:51.351Z
close_reason: "fixed in `d5ea44d` (suggestion; ID assigned in reading order): columns from `table_xinfo` with hidden and generated columns, `STRICT` tables marked, a table whose columns shadow `rowid` keyed by another alias or its primary key"
resolution: null
duplicate_of: null
---
Severity: Suggestion. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 359-365. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A22).
