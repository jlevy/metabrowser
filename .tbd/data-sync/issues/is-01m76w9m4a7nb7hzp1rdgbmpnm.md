---
type: is
id: is-01m76w9m4a7nb7hzp1rdgbmpnm
title: "PR #359 E2: volume eligibility is checked after potentially protected traversal"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76w98xw4agt7w0m6csrsacn
hold: null
hold_until: null
created_at: 2026-11-12T03:19:50.127Z
updated_at: 2026-11-12T03:42:35.799Z
started_at: 2026-11-12T03:19:54.605Z
closed_at: 2026-11-12T03:42:35.798Z
close_reason: "Fixed in 0a6c0108: walk stops before non-system mount points from getfsstat(MNT_NOWAIT); protected home looked at for nothing. RootAdmissionTests. Reply issuecomment-6813723631."
resolution: null
duplicate_of: null
---
Medium. RootAdmission.swift:51, :63, :66. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5868421803.
