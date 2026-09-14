---
type: is
id: is-01m2gb3pfd368gdf1ragzqezbg
title: "Flaky tests/test_serve_open_race.py under load: sleeps race a readiness timeout"
kind: bug
status: open
priority: 1
version: 1
labels:
  - testing
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-09-14T16:13:25.351Z
updated_at: 2026-09-14T16:13:25.351Z
---
test_wait_for_http_ok_then_open_blocks_until_http_ok failed once in make verify at load average ~40 and passed alone: a binder thread sleeps 0.4 s before binding while the readiness helper polls with a 5 s timeout, so a starved binder thread misses the deadline. Other tests in the file also depend on wall-clock (a 0.2 s timeout against a live 302 server, elapsed >= 0.3). Make the file deterministic: coordinate with events or a fake clock, assert that the CLI opens the browser only after the index route answers OK, and prove it with a negative control.
