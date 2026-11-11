---
type: is
id: is-01m74w0x4wn771sg01zxvx9dn5
title: "PR #348 D1: idle preparation cost set by origin, adds Git fetches to later refreshes"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:35.611Z
updated_at: 2026-11-11T10:57:49.383Z
started_at: 2026-11-11T09:24:56.003Z
closed_at: 2026-11-11T10:57:49.382Z
close_reason: "Fixed: c5fc056d (idle preparation only where a store is attached; fetches only the PR head and base), 10b7dafa (measurement beside the trigger), 9163be07 (docs and spec state the trade-off: the first Changes on a checkout without a store pays the acquisition). Measured with the reviewer's harness: Conversation-only session 0 Git calls and no store (was 21 + 22/18 with 1-2 origin fetches); with a store, the idle job runs exactly two fetches (refs/pull/9/head and the base commit). Tests: test_conversation_alone_never_creates_a_store_or_runs_git, test_idle_comparison_fetches_only_its_pull_request_into_the_attached_store."
resolution: null
duplicate_of: null
---
High. checkout.py:369-412; acquire.py:556-567; origin.py:27-30; pulls.py:955-968; docs/reviewing-pull-requests.md:84-86. Review D https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855776380
