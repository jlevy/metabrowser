---
type: is
id: is-01m76pnbhybp1b15p4chq0sjp8
title: "PR #359 A2: the session-file read is not bounded"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76pmzm35hysy66g7kva9k09
hold: null
hold_until: null
created_at: 2026-11-12T01:41:23.133Z
updated_at: 2026-11-12T01:41:32.434Z
started_at: 2026-11-12T01:41:32.433Z
---
Medium. apps/macos/Sources/ShellCore/Folders/SavedSession.swift:142. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702050. Same fix as B2 and C3.
