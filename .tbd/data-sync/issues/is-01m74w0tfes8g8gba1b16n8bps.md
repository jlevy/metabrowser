---
type: is
id: is-01m74w0tfes8g8gba1b16n8bps
title: "PR #348 B1: idle preparation holds the store turn and a network slot through acquisition"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:32.877Z
updated_at: 2026-11-11T10:57:50.012Z
started_at: 2026-11-11T09:24:55.957Z
closed_at: 2026-11-11T10:57:50.011Z
close_reason: "Fixed: c5fc056d. Idle work starts only while no pull job of the checkout runs, holds no network slot, and any reader's start ends it (same PR Changes promotes, its Refresh cancels the idle phase, another PR's job cancels it). Test: test_a_readers_request_never_waits_for_idle_comparison_work[another_pull, refresh, changes]. Docstring in sidekick.py reworded in 9163be07."
resolution: null
duplicate_of: null
---
Medium. checkout.py:533-537, 486-487; mirror_refresh.py:556-571, 82; sidekick.py:356-357; pull_route.py:614-633. Review B https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855560340
