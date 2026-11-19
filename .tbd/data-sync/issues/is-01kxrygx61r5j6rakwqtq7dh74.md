---
type: is
id: is-01kxrygx61r5j6rakwqtq7dh74
title: Build VS Code extension host
kind: feature
status: open
priority: 3
version: 10
spec_path: docs/project/research/archive/research-2026-07-17-vscode-extension-host.md
labels:
  - editor
  - integration
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-07-17T21:08:07.489Z
updated_at: 2026-11-19T16:49:36.608Z
extensions:
  linear:
    id: eafd0be0-c2a0-416c-b4e5-b5f56d593db2
    linked_at: 2026-08-16T08:06:21.773Z
---
Build the native tree, embedded content panel, supervised authenticated Metabrowser server, verified uv installation, and packaged workbench test coverage described by the maintained architecture document.

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): docs/project/architecture/arch-vscode-extension-host.md uses a SameSite session cookie, which has the same cross-port exposure on one loopback host; revisit with mb-qzny's choice.

2026-11-11, from review B on jlevy/metabrowser#352 (fixed in 5136540f): the VS Code host's validation should include the same cross-port credential check as mb-qzny.

2026-11-11, from review C on jlevy/metabrowser#352 (fixed in 3669a358), superseding the earlier credential notes: a per-server host name would not fix the VS Code host's cookie either (cookies are not port-bound); revisit with mb-qzny's header-token design.

2026-11-19: spec_path moved from docs/project/architecture/arch-vscode-extension-host.md, which no longer exists, to docs/project/research/archive/research-2026-07-17-vscode-extension-host.md. Restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md): its step H9 puts the VS Code host on the same host contract after H8, the token (mb-qzny), whose header-token design the notes above wait on, so this bead now waits on mb-qzny.
