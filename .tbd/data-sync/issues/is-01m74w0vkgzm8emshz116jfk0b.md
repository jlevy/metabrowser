---
type: is
id: is-01m74w0vkgzm8emshz116jfk0b
title: "PR #348 B4: reservation waiter deadline can expire while owner works; error names no lock"
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
created_at: 2026-11-11T08:36:34.031Z
updated_at: 2026-11-11T09:24:57.964Z
started_at: 2026-11-11T09:24:55.979Z
closed_at: 2026-11-11T09:24:57.964Z
close_reason: "Fixed in 5eb97c03: RESERVATION_WAIT_S = 2 x (probe + fetch deadline + 60 s), the owner's worst case with clone fallback; the failure names locks/sources/<key>.acquire.lock. test_a_cold_open_waits_out_the_owners_worst_case_and_names_the_lock."
resolution: null
duplicate_of: null
---
Low. acquire.py:1148-1157, 1121-1134; checkout.py:402-412. Review B https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855560340
