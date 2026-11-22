---
type: is
id: is-01m82c8bd5hw5cyz98wty5qm63
title: "Nightly soak time-limits red since 2026-11-19: chrome 1/4, goldens-and-serial 1/2, unit 3.14t 2/2 p90 past 80% of their limits"
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/698
    at: 2026-11-22T21:09:42.919Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
hold: null
hold_until: null
created_at: 2026-11-22T19:38:15.330Z
updated_at: 2026-11-22T21:09:42.922Z
started_at: 2026-11-22T19:55:40.236Z
---
make ci-report --check fails the nightly soak (latest run 45023473576 on 48397f596): chrome (*, 1/4) p90 6.3-6.5 of 7 min; goldens and serial (3.12/3.14/3.14t, 1/2) p90 4.2-4.3 of 5 min; unit (3.14t, 2/2) p90 6.0 of 7 min. Rebalance shards or make the slowest tests cheaper so main's soak is green for the release candidate. Related: mb-ohsk.
