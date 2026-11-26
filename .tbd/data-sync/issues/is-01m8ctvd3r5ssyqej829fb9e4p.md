---
type: is
id: is-01m8ctvd3r5ssyqej829fb9e4p
title: Use shared progress and table components for collections
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwjx1z7rpzb8emdknjxk1
hold: null
hold_until: null
created_at: 2026-11-26T21:05:44.054Z
updated_at: 2026-11-26T21:17:01.421Z
started_at: 2026-11-26T21:06:48.943Z
closed_at: 2026-11-26T21:17:01.417Z
close_reason: null
resolution: null
duplicate_of: null
---
Share the Files scan progress, SQLite table catalog, grid links and parent navigation with collection folders; verify cold and warm indexing states.

## Notes

Committed as e3d116173. Verified 112 focused tests, 18 transcript cases, repo lint/parity, and the installed distribution. Chrome matched the Files progress paint and opened the original dataset's 577-record People table through the shared catalog. Publishing follows the full handoff gate.
