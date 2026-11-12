---
type: is
id: is-01m76pnd72d49k3dphqxkmed54
title: "PR #359 B2: the session byte limit does not bound the read"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76pmzm35hysy66g7kva9k09
hold: null
hold_until: null
created_at: 2026-11-12T01:41:24.833Z
updated_at: 2026-11-12T01:53:57.198Z
started_at: 2026-11-12T01:41:33.803Z
closed_at: 2026-11-12T01:53:57.197Z
close_reason: "Fixed in f6623bd5: SessionStore.load opens once (O_NOFOLLOW|O_NONBLOCK), requires a regular file via fstat, reads at most byteLimit+1 bytes. SessionStoreTests growth, replacement, pipe and link cases. Reply on #359."
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/ShellCore/Folders/SavedSession.swift:146. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702230. Same fix as A2 and C3.
