---
type: is
id: is-01m7v68yrjfnd63q2t08xdjj9k
title: "PR #617 A6: untrusted-database hardening incomplete; wrong library-version flag"
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
created_at: 2026-11-20T00:39:02.673Z
updated_at: 2026-11-20T00:58:46.029Z
started_at: 2026-11-20T00:39:17.308Z
closed_at: 2026-11-20T00:58:46.029Z
close_reason: "fixed in `d5ea44d`: authorizer admitting only reads, the adapter's functions and pragmas (denying `ATTACH`); `DEFENSIVE`, `cell_size_check`, `mmap_size=0`, and named limits; virtual tables in their own group, shadow tables under `internal`, never queried under the untrusted profile and elsewhere only past a minimum library version in code; the 3.51.3 flag replaced by a library-version table in code; dedicated security review for the SQLite phase. Confirmed in `fda5f4c` (results/encoding.json: `trusted_schema` defaults on, FTS5 table and shadow tables read with it off)"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 349-350, 368-370, 456-464. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A6).
