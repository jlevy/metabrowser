---
type: is
id: is-01m7v694mjjpe1r2vx78m4b77a
title: "PR #617 A19: generation token can be made exact cheaply"
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
created_at: 2026-11-20T00:39:08.690Z
updated_at: 2026-11-20T00:58:50.364Z
started_at: 2026-11-20T00:39:21.806Z
closed_at: 2026-11-20T00:58:50.364Z
close_reason: "fixed in `d5ea44d`: the generation adds the `-wal` header's checkpoint sequence and salts (bytes 12-24); Info fields come from pragmas on the connection. Confirmed in `fda5f4c` (results/generation.json: 200 restarts, 2 distinct log sizes, 200 distinct headers)"
resolution: null
duplicate_of: null
---
Severity: Low. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 372-375. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A19).
