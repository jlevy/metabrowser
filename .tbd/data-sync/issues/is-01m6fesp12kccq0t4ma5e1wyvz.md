---
type: is
id: is-01m6fesp12kccq0t4ma5e1wyvz
title: "PR #283 C7: a store-owned boundary goes stale once the checkout unshallows"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T01:01:24.385Z
updated_at: 2026-11-03T01:54:05.279Z
started_at: 2026-11-03T01:33:08.138Z
closed_at: 2026-11-03T01:54:05.278Z
close_reason: "fixed in dac71d03c1b6f51222235a4c70f946f9e6982ecd on PR #283: C7 stale owned boundary dropped once the checkout is complete"
resolution: null
duplicate_of: null
---
Low. Review C. pull_refs.py:250-252; served_mirror._has_boundary.
