---
type: is
id: is-01m7x9hh4aq2anj3tkj68rymyx
title: "CI: re-measure the split goldens-and-serial jobs against their 5-minute cap after ten main runs"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
hold: null
hold_until: null
created_at: 2026-11-20T20:14:38.217Z
updated_at: 2026-11-25T02:26:07.597Z
started_at: 2026-11-20T22:58:10.663Z
---
#669 split goldens and serial into two parts per interpreter with timeout-minutes 5, set from one PR run (161-200 s). On main run 44807768998 (5f241bdbd) the parts took 153-278 s; 3.14t 2/2 took 278 s (goldens 170, serial 58, Set up Node 31 against a usual 5). ci.yml's rule is about 1.5x the measured 90th percentile. After about ten main runs, run make ci-report and set the cap and its comment from the 90th percentile, or rebalance the parts (part 2 carried 170 s of goldens to part 1's 138 on 3.14t).

## Notes

First three main CI runs after #669: all 24 goldens-and-serial jobs passed. Slowest jobs were 278 s (44807768998, 3.14t 2/2), 219 s (44831227659, 3.14t 1/2), and 226 s (44832111284, 3.14t 1/2). Retain the 5-minute cap while collecting the planned sample of about ten main runs.
