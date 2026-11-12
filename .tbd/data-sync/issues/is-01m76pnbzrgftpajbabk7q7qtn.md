---
type: is
id: is-01m76pnbzrgftpajbabk7q7qtn
title: "PR #359 A3: Retry overwrites a newly requested file with the old page"
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
created_at: 2026-11-12T01:41:23.575Z
updated_at: 2026-11-12T01:53:57.881Z
started_at: 2026-11-12T01:41:32.769Z
closed_at: 2026-11-12T01:53:57.880Z
close_reason: "Fixed in e84b6298: NextPage keeps a requested page ahead of the remembered shown page through Retry, discard, and save. NextPageTests. Reply on #359."
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/Metabrowser/BrowserWindowController.swift:227. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5867702050. Same fix as C2.
