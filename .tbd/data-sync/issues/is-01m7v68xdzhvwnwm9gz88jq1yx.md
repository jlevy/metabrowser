---
type: is
id: is-01m7v68xdzhvwnwm9gz88jq1yx
title: "PR #617 A3: reading a rollback-journal database makes the owner's commits fail"
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
created_at: 2026-11-20T00:39:01.311Z
updated_at: 2026-11-20T00:58:45.109Z
started_at: 2026-11-20T00:39:16.305Z
closed_at: 2026-11-20T00:58:45.109Z
close_reason: "fixed in `d5ea44d`, picking option 1 (new Decision 10): a validated lock-free `immutable=1` read first (identity, size, mtime, header change counter, no journal at either end), falling back to `mode=ro` under the request deadline only after validation fails twice; why: measured in `fda5f4c` (results/contention.json), validated reads failed none of the owner's commits while locked reads failed up to a quarter, and refusing unindexed sorts on large tables (A4) keeps reads short enough to validate; contention test with a `busy_timeout=0` owner added"
resolution: null
duplicate_of: null
---
Severity: High. Plan docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md lines 48-50, 338, 344-346, 436-438. PR #617, review A: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5984058557 (finding A3).
