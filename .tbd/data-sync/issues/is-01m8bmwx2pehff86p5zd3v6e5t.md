---
type: is
id: is-01m8bmwx2pehff86p5zd3v6e5t
title: Bring Paraverse relationship context and record identity to the shared table view
kind: feature
status: in_progress
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/882
    at: 2026-11-26T17:34:39.979Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8amwhv15ckjw7prckfmmggr
child_order_hints:
  - is-01m8cfwqgwqeky7gxpj7pkcpnf
  - is-01m8cfwza8gpy20g971q2wjjfy
  - is-01m8cfx7jeb9v62ef8n0esaz16
hold: null
hold_until: null
created_at: 2026-11-26T10:02:27.266Z
updated_at: 2026-11-26T17:54:29.498Z
started_at: 2026-11-26T10:04:05.984Z
---
Use the existing TableSource and table renderer for SQLite, fSQLite, structured, delimited and future SoftSchema data. Fix field-specific back-reference drilldowns and improve human-readable record context without changing stable keys or workbench conventions.

## Notes

Astra and live Paraverse comparison are in https://github.com/jlevy/metabrowser/pull/882 along with record labels and field-specific back-references. Local tests: 122 Python/API and 53 CLI/browser golden cases passed.
