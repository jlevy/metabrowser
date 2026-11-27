---
type: is
id: is-01m8e9efws1ype2z1r05jn6ekz
title: "CI flake: the free-threaded Chrome shard reaches its job deadline after all tests pass"
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/919
    at: 2026-11-27T10:50:22.984Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
hold: null
hold_until: null
created_at: 2026-11-27T10:40:03.987Z
updated_at: 2026-11-27T10:50:22.985Z
started_at: 2026-11-27T10:48:35.626Z
---
Chrome (3.14t, 1/4) hit its seven-minute job deadline on main at d0e0e1e9, run 45980829790 job 140444661398. All 21 tests reported passing in 397.18 seconds before the runner cancelled. Checkout and language setup had already succeeded. The same shard hit its deadline on #380 run 45977892508 job 140435850847, where two other jobs also hit their limits.

Retry only the cancelled job once on the same main commit. If the deadline repeats, compare test duration and job overhead across runs and rebalance the shards or reduce fixture cost while retaining the same tests and checks.
