---
type: is
id: is-01m74w0vzzrswfx26efgqypdpt
title: "PR #348 B5: busy render slots make a Markdown document answer Source"
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
created_at: 2026-11-11T08:36:34.430Z
updated_at: 2026-11-11T10:57:51.897Z
started_at: 2026-11-11T09:24:55.986Z
closed_at: 2026-11-11T10:57:51.896Z
close_reason: "Fixed: eb71cdc7. One render per server at a time, waited for, and a request for the same document joins it; no busy fallback to Source. Test: test_overlapping_documents_share_one_render_and_wait_for_the_slot."
resolution: null
duplicate_of: null
---
Low. pull_snapshot.py:200, 216, 372-375. Review B https://github.com/jlevy/metabrowser/pull/348#pullrequestreview-5855560340
