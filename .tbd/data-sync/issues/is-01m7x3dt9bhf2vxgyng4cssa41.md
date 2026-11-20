---
type: is
id: is-01m7x3dt9bhf2vxgyng4cssa41
title: "CI: the goldens tier outgrew the goldens-and-serial job's 6-minute cap (457 to 825 golden commands); shard it"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T18:27:45.065Z
updated_at: 2026-11-20T18:32:21.050Z
started_at: 2026-11-20T18:32:21.049Z
---
goldens and serial (3.14t) on #663 run 44788801411 was cancelled at 6m02s with every step green: goldens 250 s (119 files, 825 commands, 958 s of file time at 4 jobs), serial 82 s. When the cap was set (run 44037230262) goldens took 77-103 s for 82 files, 457 commands, 390 s of file time. make ci-report on 2026-11-20: p90 5.0-5.8 min, 3.14t p95 6.0, against timeout-minutes 6. ci.yml's rule: a tripped cap means a tier grew by half, and the remedy is another shard or a cheaper slow test.
