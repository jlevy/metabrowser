---
type: is
id: is-01m74w0nvr50rtca9kcweygw07
title: "PR #348 A4: snapshot Markdown bounds unmeasured and do not bound render cost"
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
created_at: 2026-11-11T08:36:28.152Z
updated_at: 2026-11-11T10:57:51.276Z
started_at: 2026-11-11T09:24:55.874Z
closed_at: 2026-11-11T10:57:51.275Z
close_reason: "Fixed: eb71cdc7 and 54dac394. A whole-document work estimate charges each construct its measured worst cost; measurements beside the constants (41 shapes, worst admitted 373 ms; 1 of 447 local docs opens as Source). Tests: test_each_measured_costly_shape_at_the_cap_opens_as_source, test_ordinary_documents_are_within_the_render_bound, test_overlapping_documents_share_one_render_and_wait_for_the_slot."
resolution: null
duplicate_of: null
---
Medium. pull_snapshot.py:55, 162-172, 200, 212. Review A https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855514600
