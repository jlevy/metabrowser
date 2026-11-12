---
type: is
id: is-01m76wa04gy0crgcqe9s9y2s3r
title: "PR #359 E4: a raced diagnostic lookup can silently discard a valid tab"
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
created_at: 2026-11-12T03:20:02.397Z
updated_at: 2026-11-12T03:42:36.680Z
started_at: 2026-11-12T03:20:07.871Z
closed_at: 2026-11-12T03:42:36.679Z
close_reason: "Fixed in 0a6c0108: refusedComponent drops a tab only on proven absence; raced or failed second lookups defer. RootAdmissionTests. Reply issuecomment-6813723631."
resolution: null
duplicate_of: null
---
Medium. RootAdmission.swift:78, :79. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5868421803.
