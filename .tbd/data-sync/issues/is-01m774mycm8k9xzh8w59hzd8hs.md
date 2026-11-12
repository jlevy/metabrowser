---
type: is
id: is-01m774mycm8k9xzh8w59hzd8hs
title: "PR #359 F1: the home lookup bypasses custom mount barriers"
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
created_at: 2026-11-12T05:45:49.715Z
updated_at: 2026-11-12T05:52:09.860Z
started_at: 2026-11-12T05:45:51.257Z
closed_at: 2026-11-12T05:52:09.855Z
close_reason: "Fixed in 0fbd0c76: a home on a mount barrier defers every root before any lookup. MountTableTests.aHomeOnAMountBarrierIsNotLookedAt. Reply issuecomment-6815877435."
resolution: null
duplicate_of: null
---
Medium. RootAdmission.swift:58, :89. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5869672076.
