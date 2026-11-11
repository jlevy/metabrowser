---
type: is
id: is-01kxrygx61r5j6rakwqtq7dh74
title: Build VS Code extension host
kind: feature
status: open
priority: 3
version: 9
spec_path: docs/project/architecture/arch-vscode-extension-host.md
labels:
  - editor
  - integration
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-07-17T21:08:07.489Z
updated_at: 2026-11-11T22:51:50.501Z
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
