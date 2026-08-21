---
type: is
id: is-01m0k4p2d6xf80tn8qxhx6qavc
title: Move highlight.js, the TOML grammar, and Mustache to the prefetched tier
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T21:47:27.014Z
updated_at: 2026-08-21T23:48:52.295Z
closed_at: 2026-08-21T23:48:52.294Z
close_reason: "Landed as an idle-callback start for the prefetched chain in server.py, with PREFETCH_IDLE_TIMEOUT_MS as the floor. Measured on the 100k bench corpus, median of three cold loads: load 3,883 ms to 750 ms; time to first tree row not measurably changed (854 ms vs 999 ms, overlapping ranges). Accepted on the tier policy and the load result."
---
