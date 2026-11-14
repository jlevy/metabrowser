---
type: is
id: is-01m0nhc7jsejcaqc7ze5rnjeax
title: Break the scan/serve contention loop (H31)
kind: task
status: open
priority: 0
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T20:07:44.984Z
updated_at: 2026-11-14T18:45:19.869Z
---
exp-007 resolved most of this from the other end. Removing the per-request tally cost (mb-74ad) cut the attached walk on the real tree from 70.2s to 50.0s without touching the walker -- the requests were taking CPU the walk wanted. Combined with mb-iyat the attached walk went 258s -> 50s and amplification from ~12x to ~2.4x (unattached is 21s). What remains: measure with a REAL browser, which is heavier than probe-server (progress poll every 1s plus tree refetches plus the subtree sweep), and decide whether serving needs an explicit CPU bound during a scan or the walk should leave the serving process.

## Notes

2026-11-14 audit: exp-034 measured the walk with a real browser attached on the 300k flat corpus at 1.62-1.78x v0.9.1, against 1.13-1.30x backend-only, so a browser still roughly doubles the gap (mb-qvw4). The native-app topology research cites this bead for whether the walk should leave the serving process (docs/project/research/research-2026-11-10-native-app-server-topology.md).
