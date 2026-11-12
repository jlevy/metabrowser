---
type: is
id: is-01m76pnew8e939zhpgv6ha3mjq
title: "PR #359 C3: the session size check does not bound the actual read"
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
created_at: 2026-11-12T01:41:26.535Z
updated_at: 2026-11-12T01:53:57.533Z
started_at: 2026-11-12T01:41:35.213Z
closed_at: 2026-11-12T01:53:57.532Z
close_reason: "Fixed in f6623bd5: SessionStore.load opens once (O_NOFOLLOW|O_NONBLOCK), requires a regular file via fstat, reads at most byteLimit+1 bytes. SessionStoreTests growth, replacement, pipe and link cases. Reply on #359."
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/ShellCore/Folders/SavedSession.swift:142. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702430. Same fix as A2 and B2.
