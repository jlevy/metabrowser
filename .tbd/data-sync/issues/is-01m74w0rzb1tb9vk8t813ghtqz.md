---
type: is
id: is-01m74w0rzb1tb9vk8t813ghtqz
title: "PR #348 A12: a waiting cold open is silent; a dead owner's orphaned fetch keeps the reservation"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74w003xk59spnxy95gr9dss
hold: null
hold_until: null
created_at: 2026-11-11T08:36:31.338Z
updated_at: 2026-11-11T10:57:53.492Z
started_at: 2026-11-11T09:24:55.930Z
closed_at: 2026-11-11T10:57:53.492Z
close_reason: "Fixed: 5eb97c03 (writers inherit only the staging lock; a waiting open reports a note once; tests) and 9163be07 (sources architecture no longer says writers inherit the reservation)."
resolution: null
duplicate_of: null
---
Low. acquire.py:1141-1159, 468-473; tests/test_cache_async_locks.py:296. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
