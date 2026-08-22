---
type: is
id: is-01m0m5vy1d7k3wgz1jaxt90y0w
title: Measure the shell over --remote before touching request count (H26)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T07:27:22.156Z
updated_at: 2026-08-22T07:27:22.156Z
---
~110 requests over six HTTP/1.1 connections is ~19 serial rounds x RTT on metab --remote; at 50ms RTT roughly a second of shell before any API call. One measured remote (or tc-throttled) load sets the stake for H9/H10. If it matters, the fix is a server-side concat of eager static/*.js in tag order — no bundler, tier policy intact.
