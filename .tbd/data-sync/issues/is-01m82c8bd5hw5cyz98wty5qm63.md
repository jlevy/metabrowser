---
type: is
id: is-01m82c8bd5hw5cyz98wty5qm63
title: "Nightly soak time-limits red since 2026-11-19: chrome 1/4, goldens-and-serial 1/2, unit 3.14t 2/2 p90 past 80% of their limits"
kind: task
status: in_progress
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/698
    at: 2026-11-22T21:09:42.919Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
child_order_hints:
  - is-01m82pjfezpdfpc8a6cknpnz2m
hold: null
hold_until: null
created_at: 2026-11-22T19:38:15.330Z
updated_at: 2026-11-28T18:05:44.685Z
started_at: 2026-11-22T19:55:40.236Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
make ci-report --check fails the nightly soak (latest run 45023473576 on 48397f596): chrome (*, 1/4) p90 6.3-6.5 of 7 min; goldens and serial (3.12/3.14/3.14t, 1/2) p90 4.2-4.3 of 5 min; unit (3.14t, 2/2) p90 6.0 of 7 min. Rebalance shards or make the slowest tests cheaper so main's soak is green for the release candidate. Related: mb-ohsk.

## Notes

Nightly run 46145831492 passed all 25 repeated functional jobs. Time-limits reported chrome 3.13 shard 1/5 p90 5.6 min against 7 min, lint 2.6 against 3, and both 3.14t unit shards 5.9 and 6.1 against 7. Use per-step durations to distinguish setup stalls from test cost before recalibrating shards or changing deadlines.
