---
type: is
id: is-01m82c8bd5hw5cyz98wty5qm63
title: "Nightly soak time-limits red since 2026-11-19: chrome 1/4, goldens-and-serial 1/2, unit 3.14t 2/2 p90 past 80% of their limits"
kind: task
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/698
    at: 2026-11-22T21:09:42.919Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
child_order_hints:
  - is-01m82pjfezpdfpc8a6cknpnz2m
hold: null
hold_until: null
created_at: 2026-11-22T19:38:15.330Z
updated_at: 2026-11-28T17:47:54.076Z
started_at: 2026-11-22T19:55:40.236Z
closed_at: null
close_reason: null
resolution: null
duplicate_of: null
---
make ci-report --check fails the nightly soak (latest run 45023473576 on 48397f596): chrome (*, 1/4) p90 6.3-6.5 of 7 min; goldens and serial (3.12/3.14/3.14t, 1/2) p90 4.2-4.3 of 5 min; unit (3.14t, 2/2) p90 6.0 of 7 min. Rebalance shards or make the slowest tests cheaper so main's soak is green for the release candidate. Related: mb-ohsk.

## Notes

2026-11-22: Two stacked PRs (GitHub stack #701), neither merged. PR #698 (claude/soak-ci-shards): all three shard dealers deal heaviest-first by measured seconds from devtools/shard_weights.json (devtools/shard_weights.py); make shard-weights refreshes it from a green main run's logs (median over interpreters); unmeasured units weigh the median of those dealt with them; goldens and serial go to three parts, since two even parts took 3.9 of 5 min on 3.12/3.14t. Measured on run 45069051784: chrome 252-259 s every part (was 161-394), unit 184-245 s, goldens and serial 109-193 s. PR #700 (claude/soak-chrome-slow-tier), from the owner's directions of 2026-11-22: the plan job picks a path; a pull request while main is green runs one interpreter, the Chrome tier without tests measured at 20 s or more and only when a browser path changed, admitted-git on 2.43.7 in two parts. First run 45069289704: slowest job 189 s (about 4 min a run, was 7). Three minutes is blocked by tests/test_github_pulls.py (112 s on one worker) and 45-60 s of per-job setup and collection; splitting that file is the follow-up. After merge, confirm the nightly soak's ci-report --check is green before closing.

Reopened: The timing-headroom check regressed in nightlies 46000881330 and 46145831492. In the latter all 25 serial and Chrome soak jobs passed. The timing gate flagged peaks for Chrome, lint, and both free-threaded unit shards. Re-measure those shards and restore headroom before release preparation.
