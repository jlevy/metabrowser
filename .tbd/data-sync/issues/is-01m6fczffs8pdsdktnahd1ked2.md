---
type: is
id: is-01m6fczffs8pdsdktnahd1ked2
title: Mount a very large comparison's file list without one long task
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-03T00:29:37.144Z
updated_at: 2026-11-03T00:29:37.144Z
---
Measured on the large-PR performance layer: the mount is a single task of 262-275 ms at 44k nodes and 616-628 ms at 115k, against a proposed 200 ms; github.com took 390. A content-visibility probe did not move it (625 vs 626, 257 vs 266), so it needs batched mounting or a window, designed together with the pull-request nav. Deferred-file lines at 115k nodes (122-214 ms against 150) and the queue on a +442k-line case (813 ms against 300) are the two other open budget misses.
