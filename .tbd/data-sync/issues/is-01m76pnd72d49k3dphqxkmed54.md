---
type: is
id: is-01m76pnd72d49k3dphqxkmed54
title: "PR #359 B2: the session byte limit does not bound the read"
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
created_at: 2026-11-12T01:41:24.833Z
updated_at: 2026-11-12T01:41:33.804Z
started_at: 2026-11-12T01:41:33.803Z
---
Medium. apps/macos/Sources/ShellCore/Folders/SavedSession.swift:146. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702230. Same fix as A2 and C3.
