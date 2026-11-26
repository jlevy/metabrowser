---
type: is
id: is-01m8cg5pqdycqe1vwjjtz9xpbe
title: Keep malformed relationship filters visible to the API
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8bmwx2pehff86p5zd3v6e5t
hold: null
hold_until: null
created_at: 2026-11-26T17:59:07.234Z
updated_at: 2026-11-26T18:04:04.319Z
started_at: 2026-11-26T18:04:04.313Z
---
PR #882 correctness review found that an empty or unbound via could silently broaden the table. The browser should preserve invalid parameters so the API can report them.
