---
type: is
id: is-01m7v68xvz6h4z9h6mc1k5wb74
title: "PR #617 A4: opcode budget does not bound count(*) or unindexed sorts; no exhausted-budget envelope"
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
created_at: 2026-11-20T00:39:01.759Z
updated_at: 2026-11-20T00:58:45.402Z
started_at: 2026-11-20T00:39:16.632Z
closed_at: 2026-11-20T00:58:45.402Z
close_reason: "fixed in `d5ea44d`: a wall-clock deadline via `Connection.interrupt()` beside the progress handler; counts as `count(*) FROM (SELECT 1 … LIMIT cap+1)`; `schema()` marks fields unsortable past a measured row count with `sort_note`; exhausted-budget envelope (partial key-ordered scan with `complete: false` and rows examined, refusal for a sort); seek claims and the bounds test corrected. Confirmed in `fda5f4c` (results/budget.json): `count(*)` is 9 opcodes and never reaches a 1,000-opcode handler; unindexed sort pages cost 1.4 to 1.9 million opcodes versus about 1,000 indexed"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 270-276, 347-348, 515-521, 598-599. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A4).
