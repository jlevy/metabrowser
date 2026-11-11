---
type: is
id: is-01m74w0pmweetmcjb7xr6eq909
title: "PR #348 A6: callers' handling of a lost publication is untested"
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
created_at: 2026-11-11T08:36:28.955Z
updated_at: 2026-11-11T10:57:52.859Z
started_at: 2026-11-11T09:24:55.887Z
closed_at: 2026-11-11T10:57:52.858Z
close_reason: "Fixed: e190083a (refresh_pull_request and ServedPull.refresh adopt the winner and its stamp), c5fc056d (checkout job adoption test), c10f4f80 (open_pull_request head_mismatch outcome; #347's swap tests pin the other two)."
resolution: null
duplicate_of: null
---
Medium. pulls.py:1058-1063, 1144-1153; served_pull.py:388-401; checkout.py:511-516. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
