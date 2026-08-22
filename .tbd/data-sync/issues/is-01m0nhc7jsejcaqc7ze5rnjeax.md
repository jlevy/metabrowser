---
type: is
id: is-01m0nhc7jsejcaqc7ze5rnjeax
title: Break the scan/serve contention loop (H31)
kind: task
status: open
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:44.984Z
updated_at: 2026-08-22T22:12:42.355Z
---
exp-007 resolved most of this from the other end. Removing the per-request tally cost (mb-74ad) cut the attached walk on the real tree from 70.2s to 50.0s without touching the walker -- the requests were taking CPU the walk wanted. Combined with mb-iyat the attached walk went 258s -> 50s and amplification from ~12x to ~2.4x (unattached is 21s). What remains: measure with a REAL browser, which is heavier than probe-server (progress poll every 1s plus tree refetches plus the subtree sweep), and decide whether serving needs an explicit CPU bound during a scan or the walk should leave the serving process.
