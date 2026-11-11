---
type: is
id: is-01m7594s4k2r6vkqdpnhbk6yvb
title: "PR #348 E4: Changes waits for a failing idle attempt it promoted, then repeats it"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7594pkfe0xdkwhjqrwwpxz2
hold: null
hold_until: null
created_at: 2026-11-11T12:25:54.066Z
updated_at: 2026-11-11T14:23:37.875Z
started_at: 2026-11-11T12:25:54.668Z
closed_at: 2026-11-11T14:23:37.874Z
close_reason: "Fixed: f9f7b9c3. A promoted idle phase returns its failure; the reader's job keeps it without a second attempt, and an uncertain base goes on to be deepened. Test: test_changes_that_promoted_a_failing_idle_fetch_does_not_repeat_it (one fetch; fails without the change)."
resolution: null
duplicate_of: null
---
Low. checkout.py:394-403, 564-567, 649-660. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040
