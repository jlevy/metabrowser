---
type: is
id: is-01m74w0tvdayh8karsm9yw9dps
title: "PR #348 B2: store bind in preparation clears observed_reader, nothing restores it"
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
created_at: 2026-11-11T08:36:33.260Z
updated_at: 2026-11-11T09:24:57.644Z
started_at: 2026-11-11T09:24:55.966Z
closed_at: 2026-11-11T09:24:57.643Z
close_reason: "Fixed in c5fc056d: ServedPulls.bind keeps observed_reader for a same-source rebind; cached_comparison_record admits nothing without an observed reader. test_attaching_a_store_keeps_the_observed_reader_for_reader_scoped_checks covers the bind, the comparison/idle record check, snapshot admission, core admission (cached_batch) and cached-core reads, with the None mutation."
resolution: null
duplicate_of: null
---
Medium. checkout.py:487, 492; served_pull.py:516-525; pull_route.py:590, 387; pull_snapshot.py:133; sidekick.py:99-108; pull_cores.py:246. Review B https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855560340
