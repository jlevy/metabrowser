---
type: is
id: is-01m76pnew8e939zhpgv6ha3mjq
title: "PR #359 C3: the session size check does not bound the actual read"
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
created_at: 2026-11-12T01:41:26.535Z
updated_at: 2026-11-12T01:41:35.214Z
started_at: 2026-11-12T01:41:35.213Z
---
Medium. apps/macos/Sources/ShellCore/Folders/SavedSession.swift:142. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702430. Same fix as A2 and B2.
