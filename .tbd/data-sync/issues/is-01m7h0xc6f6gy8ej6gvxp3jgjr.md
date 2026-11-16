---
type: is
id: is-01m7h0xc6f6gy8ej6gvxp3jgjr
title: "PR #455 A8: two helpers compute what the server sends a gzip client"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:52:56.014Z
updated_at: 2026-11-16T02:11:17.821Z
started_at: 2026-11-16T01:53:13.220Z
closed_at: 2026-11-16T02:11:17.820Z
close_reason: "A8 fixed in 5ba8a1846: check_startup_scripts calls delivery.sent_size and refuses a middleware set apart from it; test added."
resolution: null
duplicate_of: null
---
Severity: Low. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review A (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5913913966), finding A8. References: devtools/check_startup_scripts.py:250-271; src/metabrowser/delivery.py:154-158.
