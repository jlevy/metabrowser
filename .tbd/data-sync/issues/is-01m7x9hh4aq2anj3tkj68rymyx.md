---
type: is
id: is-01m7x9hh4aq2anj3tkj68rymyx
title: "CI: re-measure the split goldens-and-serial jobs against their 5-minute cap after ten main runs"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-20T20:14:38.217Z
updated_at: 2026-11-20T20:14:38.217Z
---
#669 split goldens and serial into two parts per interpreter with timeout-minutes 5, set from one PR run (161-200 s). On main run 44807768998 (5f241bdbd) the parts took 153-278 s; 3.14t 2/2 took 278 s (goldens 170, serial 58, Set up Node 31 against a usual 5). ci.yml's rule is about 1.5x the measured 90th percentile. After about ten main runs, run make ci-report and set the cap and its comment from the 90th percentile, or rebalance the parts (part 2 carried 170 s of goldens to part 1's 138 on 3.14t).
