---
type: is
id: is-01m76w9stdk55gkrp17b25z0wb
title: "PR #359 E3: embedded NULs bypass the protection check before openat"
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
created_at: 2026-11-12T03:19:55.958Z
updated_at: 2026-11-12T03:42:36.224Z
started_at: 2026-11-12T03:20:01.625Z
closed_at: 2026-11-12T03:42:36.223Z
close_reason: "Fixed in 0a6c0108: NUL-holding saved paths are invalid before any lookup. RootAdmissionTests.aPathWithANulIsRefusedUnlooked. Reply issuecomment-6813723631."
resolution: null
duplicate_of: null
---
Medium. RootAdmission.swift:95, :51. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5868421803.
