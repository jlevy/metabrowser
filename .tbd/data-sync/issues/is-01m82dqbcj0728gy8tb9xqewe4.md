---
type: is
id: is-01m82dqbcj0728gy8tb9xqewe4
title: Open pull request page shows GitHub changes within seconds, not up to 90 s
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-22T20:03:55.409Z
updated_at: 2026-11-22T20:04:03.356Z
started_at: 2026-11-22T20:04:03.347Z
---
A merge on github.com took 48 s to show on an open, visible pull request page (fdu #214, 2026-11-22: merged 19:29:37, shown 19:30:25). The page polls the server every SLOW_POLL_MS (30 s) and the server treats a record as fresh for FRESHNESS_WINDOW_S (60 s), so a change can take up to ~90 s. Goal: while a pull request page is visible, check GitHub for that pull request every few seconds with a cheap conditional request, refresh the record when it changed, and show it at once.
