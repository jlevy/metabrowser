---
type: is
id: is-01m7v6913h13kd5ncnhqh0kqv9
title: "PR #617 A11: deserializing a WAL Git blob fails; Git content bypasses api_file magic check"
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
created_at: 2026-11-20T00:39:05.073Z
updated_at: 2026-11-20T00:58:47.699Z
started_at: 2026-11-20T00:39:19.027Z
closed_at: 2026-11-20T00:58:47.698Z
close_reason: "fixed in `d5ea44d`: Git blobs are deserialized with header bytes 18-19 set to rollback mode and the Info view says the log is not included; `magic` is checked at `api_file`, `classify_identity`, `_resolve_container_child`, and `--show`; a compressed database stays binary. Confirmed in `fda5f4c` (deserializing `02 02` fails `SQLITE_CANTOPEN`; patched `01 01` reads)"
resolution: null
duplicate_of: null
---
Severity: Medium. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 306-309, 342, 571, 577. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A11).
