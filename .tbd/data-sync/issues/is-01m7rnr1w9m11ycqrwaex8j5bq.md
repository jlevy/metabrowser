---
type: is
id: is-01m7rnr1w9m11ycqrwaex8j5bq
title: "Flaky: test_present real-server test binds the default port 8411 and collides with parallel workers"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-19T01:11:42.728Z
updated_at: 2026-11-19T01:33:31.675Z
started_at: 2026-11-19T01:12:06.136Z
closed_at: 2026-11-19T01:33:31.674Z
close_reason: "Landed in #594"
resolution: null
duplicate_of: null
---
tests/test_present.py::test_a_real_server_serves_the_target_detached_until_killed starts a real server on settings.DEFAULT_BROWSER_PORT (8411) and fails with 'address already in use' when another xdist worker holds it. Seen on main at db33e16d2 (run 44428746215, unit 3.12 1/2) and on #581 and #590. Came in with #582.
