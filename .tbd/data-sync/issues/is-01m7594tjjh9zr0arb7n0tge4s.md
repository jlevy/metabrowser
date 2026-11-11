---
type: is
id: is-01m7594tjjh9zr0arb7n0tge4s
title: "PR #348 E6: Changes holds a network slot while waiting for another process's reservation"
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
created_at: 2026-11-11T12:25:55.537Z
updated_at: 2026-11-11T14:23:38.514Z
started_at: 2026-11-11T12:25:56.147Z
closed_at: 2026-11-11T14:23:38.513Z
close_reason: "Fixed: f9f7b9c3. Changes waits for another process's reservation with no slot (wait_for_source_reservation), then takes one for the acquisition; AcquiringElsewhereError reports refreshing_elsewhere naming the lock file. Test: test_changes_waits_for_another_process_cold_open_without_a_network_slot (fails with the wait inside the slot)."
resolution: null
duplicate_of: null
---
Low. checkout.py:455-464, 612-617, 682-683; acquire.py:173, 1116, 1149-1182. Review E https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5858632040
