---
type: is
id: is-01m6fpn1bjpdgch47hnjnh0kqr
title: "PR #281 D1: StoreTurn counts firsts that went ahead of nothing, so the documented order fails on the first contention"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:40.753Z
updated_at: 2026-11-03T03:18:48.959Z
started_at: 2026-11-03T03:18:48.958Z
---
Medium. src/metabrowser/mirror_refresh.py:535-539: _give increments _first_in_a_row whenever the chosen waiter goes first, also when no other waits. Fix: count only firsts that went ahead of a waiting other; add a test that inflates the counter before the contention. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
