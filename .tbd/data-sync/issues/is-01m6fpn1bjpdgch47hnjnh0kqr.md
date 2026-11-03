---
type: is
id: is-01m6fpn1bjpdgch47hnjnh0kqr
title: "PR #281 D1: StoreTurn counts firsts that went ahead of nothing, so the documented order fails on the first contention"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:40.753Z
updated_at: 2026-11-03T04:10:43.809Z
started_at: 2026-11-03T03:18:48.958Z
closed_at: 2026-11-03T04:10:43.808Z
close_reason: "Fixed in 9fb6d138: StoreTurn._give counts a first only when it went ahead of a waiting job. Confirmed by test_jobs_that_went_first_with_nothing_waiting_do_not_hold_back_the_next_first (both warm-ups; fails without the fix at ['mirror', 'pull 8']) and the review's probe (order now ... pull 7, counter 0). CI 41574482948 green at 24deeb22."
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/mirror_refresh.py:535-539: _give increments _first_in_a_row whenever the chosen waiter goes first, also when no other waits. Fix: count only firsts that went ahead of a waiting other; add a test that inflates the counter before the contention. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
