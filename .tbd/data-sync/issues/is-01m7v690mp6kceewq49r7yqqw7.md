---
type: is
id: is-01m7v690mp6kceewq49r7yqqw7
title: "PR #617 A10: a directory cannot be a plugin kind; folder_marker does not make it one"
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
created_at: 2026-11-20T00:39:04.597Z
updated_at: 2026-11-20T00:58:47.357Z
started_at: 2026-11-20T00:39:18.698Z
closed_at: 2026-11-20T00:58:47.357Z
close_reason: 'fixed in `d5ea44d`, picking option 1: `fsqlite.json` is the `sqlite-store` kind (`folder_marker` plus `json_has_key = "format"` / `json_value_prefix = "fsqlite"`), so the folder is badged and the marker opens the store with no core change; why: it needs no fourth framework change; fsqlite transients never take the lock-taking fallback'
resolution: null
duplicate_of: null
---
Severity: Medium. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 377-381. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A10).
