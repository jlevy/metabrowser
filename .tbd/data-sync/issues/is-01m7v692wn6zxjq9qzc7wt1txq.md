---
type: is
id: is-01m7v692wn6zxjq9qzc7wt1txq
title: "PR #617 A15: several claims about current code are wrong"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7v68w30f9d3dts3s8ga3rkz
hold: null
hold_until: null
created_at: 2026-11-20T00:39:06.901Z
updated_at: 2026-11-20T00:58:49.056Z
started_at: 2026-11-20T00:39:20.384Z
closed_at: 2026-11-20T00:58:49.056Z
close_reason: 'fixed in `d5ea44d`: `.data-table` stated as unused and deleted, the folder Distribution and totals `file-type-summary-table` tables named as adopting the Data Tables rules; the "databases are usually ignored" claim dropped for what the stream actually covers; the registry change stated as moving `db` from `configuration` to the `sqlite` kind (verified in `recommended-file-types.toml`)'
resolution: null
duplicate_of: null
---
Severity: Medium. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 89-91, 104-106, 313, 451-454, 561-562. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A15).
