---
type: is
id: is-01m74w0xh230gf3xepr88zed40
title: "PR #348 D2: store turn anti-starvation lets a queued idle job go ahead of foreground"
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
created_at: 2026-11-11T08:36:36.001Z
updated_at: 2026-11-11T09:24:58.628Z
started_at: 2026-11-11T09:24:56.009Z
closed_at: 2026-11-11T09:24:58.628Z
close_reason: "Fixed in c5fc056d: idle work starts only while no pull job of the checkout runs, and any reader's start cancels or promotes it, so it is never queued with or ahead of a reader. test_idle_comparison_is_never_queued_with_or_ahead_of_a_readers_job (review D's ordering: 12, 13, 14, 15)."
resolution: null
duplicate_of: null
---
Medium. checkout.py:533-534; mirror_refresh.py:519-522, 561-562, 99. Review D https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855776380
