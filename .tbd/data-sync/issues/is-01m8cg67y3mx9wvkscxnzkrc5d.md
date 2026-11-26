---
type: is
id: is-01m8cg67y3mx9wvkscxnzkrc5d
title: Mark SQLite reverse counts incomplete for previewed target values
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8bmwx2pehff86p5zd3v6e5t
hold: null
hold_until: null
created_at: 2026-11-26T17:59:24.858Z
updated_at: 2026-11-26T18:04:34.374Z
started_at: 2026-11-26T18:04:04.350Z
closed_at: 2026-11-26T18:04:34.374Z
close_reason: "Fixed and independently rechecked on the shared-table PR #882 head 4292cb856."
resolution: null
duplicate_of: null
---
PR #882 correctness review reproduced a false exact zero for referencing an oversized UNIQUE value. Preserve SQLite limits while reporting a lower bound.
