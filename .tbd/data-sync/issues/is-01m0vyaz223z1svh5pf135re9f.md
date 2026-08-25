---
type: is
id: is-01m0vyaz223z1svh5pf135re9f
title: "PR #74 review MB74-D1: represent an open idle inventory honestly"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m0vyaj3yjgs2p8mvt4y41b43
hold: null
hold_until: null
created_at: 2026-08-25T07:49:41.569Z
updated_at: 2026-08-25T07:49:47.204Z
started_at: 2026-08-25T07:49:47.204Z
---
The LifecyclePhase enum has no READY phase. python_inventory.py reports WATCHING even when watch_mode=off. Add the state and legal transitions, map the reference provider honestly, update contract/docs/tests, and preserve monotonic lifecycle behavior. Origin: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5407035634
