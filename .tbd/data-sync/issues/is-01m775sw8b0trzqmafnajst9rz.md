---
type: is
id: is-01m775sw8b0trzqmafnajst9rz
title: "PR #359 G1: sandboxed raw documents can repeatedly open native print panels"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m775svs86787wz3havqdty4f
hold: null
hold_until: null
created_at: 2026-11-12T06:05:59.946Z
updated_at: 2026-11-12T06:10:42.755Z
started_at: 2026-11-12T06:06:01.034Z
closed_at: 2026-11-12T06:10:42.754Z
close_reason: "Fixed in 7dae3a6e: PagePrintRequests.allows authorizes by frame.securityOrigin, refusing opaque origins; red executed against the URL check (accepted.count 6), green after. Reply issuecomment-6816177729."
resolution: null
duplicate_of: null
---
Medium. apps/macos/Sources/Metabrowser/BrowserWindowController.swift:288, apps/macos/Sources/ShellCore/Web/PagePrint.swift:30 and :43. Review https://github.com/jlevy/metabrowser/pull/359#pullrequestreview-5869848796.
