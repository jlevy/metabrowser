---
type: is
id: is-01m6fpmhz6r19d3a9dhkm4v5j4
title: "PR #283 D5: the /api/source/status row does not say ref_on_origin is null for a swept ref"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T03:18:24.997Z
updated_at: 2026-11-03T03:28:54.190Z
started_at: 2026-11-03T03:18:37.774Z
closed_at: 2026-11-03T03:28:54.189Z
close_reason: "fixed in 0098e113 on PR #283: D5 status row and field comment describe a swept ref's null"
resolution: null
duplicate_of: null
---
Low. Review D, PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. mirror_refresh.py:559-563 answers None for a ref the store swept; arch-views-models-routes.md line 154 says null is only a pin by commit ID or a ref not yet observed, and source_routes.py:129 has no comment.
