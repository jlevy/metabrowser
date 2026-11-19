---
type: is
id: is-01m7rnr1w9m11ycqrwaex8j5bq
title: "Flaky: test_present real-server test binds the default port 8411 and collides with parallel workers"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T01:11:42.728Z
updated_at: 2026-11-19T01:11:42.728Z
---
tests/test_present.py::test_a_real_server_serves_the_target_detached_until_killed starts a real server on settings.DEFAULT_BROWSER_PORT (8411) and fails with 'address already in use' when another xdist worker holds it. Seen on main at db33e16d2 (run 44428746215, unit 3.12 1/2) and on #581 and #590. Came in with #582.
