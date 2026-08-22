---
type: is
id: is-01m0nw8hkn680qwx3zrxf6qbgq
title: Guard the wins with a generous CI perf threshold (S8)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:58.516Z
updated_at: 2026-08-22T23:17:58.516Z
---
Review suggestion S8. These numbers are measured once, at review time; nothing stops 21.4s -> 2.2s from quietly coming back. probe-server already samples routes without a browser, so a small committed corpus plus a deliberately generous threshold (fail at ~3x the recorded median) would catch an order-of-magnitude regression without making CI flaky on ordinary variance.
