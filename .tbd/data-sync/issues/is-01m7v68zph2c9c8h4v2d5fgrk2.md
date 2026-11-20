---
type: is
id: is-01m7v68zph2c9c8h4v2d5fgrk2
title: "PR #617 A8: plan ignores the existing container contract for a database's tables"
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
created_at: 2026-11-20T00:39:03.633Z
updated_at: 2026-11-20T00:58:46.699Z
started_at: 2026-11-20T00:39:18.020Z
closed_at: 2026-11-20T00:58:46.699Z
close_reason: "fixed in `d5ea44d`: new Decision 9 recommends the container contract; SQLite and fsqlite kinds declare `container = { children = \"tables\" }`, the container page is the Info and Schema overview, a table is `<db>/<table>` and `metab --show app.db/users` names it; the in-view table list is removed. One refinement: the open record is query state (`record=<key>`) on the table's address rather than a `/<key>` segment, so every source, single-table ones included, uses one rule for an opaque key"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 278-294, 398-405. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A8).
