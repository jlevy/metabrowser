---
type: is
id: is-01m7v695gz0zhe81nz2ajbf5hj
title: "PR #617 A21: offer a cheap count estimate beside a lower bound (sqlite_stat1 or max rowid)"
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
created_at: 2026-11-20T00:39:09.598Z
updated_at: 2026-11-20T00:58:51.016Z
started_at: 2026-11-20T00:39:22.503Z
closed_at: 2026-11-20T00:58:51.016Z
close_reason: "fixed in `d5ea44d` (suggestion; ID assigned in reading order): the envelope adds `estimate` from `sqlite_stat1` or the largest rowid, drawn as approximate beside a lower bound"
resolution: null
duplicate_of: null
---
Severity: Suggestion. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 264-268, 515-521. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A21).
