---
type: is
id: is-01m774myvcsmqs4fvfhh65n614
title: "PR #359 F2: mount-table growth is accepted as a complete barrier list"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m774mxyawk9866c969b4qnmv
hold: null
hold_until: null
created_at: 2026-11-12T05:45:50.187Z
updated_at: 2026-11-12T05:52:10.454Z
started_at: 2026-11-12T05:45:51.654Z
closed_at: 2026-11-12T05:52:10.453Z
close_reason: "Fixed in 0fbd0c76: mountPoints(fsstat:) allocates spare room, rereads a saturated fill into a larger buffer (bounded), and returns nil when the table cannot be read whole. MountTableTests. Reply issuecomment-6815877435."
resolution: null
duplicate_of: null
---
Medium. RootAdmission.swift:112, :118. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5869672076.
