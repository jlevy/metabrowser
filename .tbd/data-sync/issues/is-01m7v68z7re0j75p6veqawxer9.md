---
type: is
id: is-01m7v68z7re0j75p6veqawxer9
title: "PR #617 A7: /api/watch adds a second long-lived connection per page"
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
created_at: 2026-11-20T00:39:03.160Z
updated_at: 2026-11-20T00:58:46.367Z
started_at: 2026-11-20T00:39:17.671Z
closed_at: 2026-11-20T00:58:46.367Z
close_reason: "fixed in `d5ea44d`: Decision 4 gains option C, recommended: watches registered on the page's existing `/api/events` connection, server stat-polls registered paths the inventory does not deliver and sends `file.changed`, bounded per connection, under `shell.page-connections`, Git pin answered as `/api/events` does, and `/api/stream` stays separate"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 315-324, 496-504. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A7).
