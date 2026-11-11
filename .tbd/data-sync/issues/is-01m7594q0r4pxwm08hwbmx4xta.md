---
type: is
id: is-01m7594q0r4pxwm08hwbmx4xta
title: "PR #348 E1: idle preparation publishes a failed comparison into the shared record"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7594pkfe0xdkwhjqrwwpxz2
hold: null
hold_until: null
created_at: 2026-11-11T12:25:51.895Z
updated_at: 2026-11-11T14:23:36.916Z
started_at: 2026-11-11T12:25:52.494Z
closed_at: 2026-11-11T14:23:36.909Z
close_reason: "Fixed: f9f7b9c3. prepare_pull_comparison(optional=True) publishes only a computed comparison; failures raise, an uncertain base raises NeedsDeepening without writing or deepening. Tests: test_a_failed_idle_comparison_leaves_the_shared_record_as_it_was, test_idle_work_never_deepens_an_uncertain_base (both fail with optional=True dropped)."
resolution: null
duplicate_of: null
---
Medium. checkout.py:531-571; pulls.py:855-876, 891-911. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040
