---
type: is
id: is-01m75sahhp1nbm15h57bjb9bvp
title: App requires a compatible metab version and notices upgrades
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1y7vycw6kpfkcegtp4zh
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T17:08:40.117Z
updated_at: 2026-11-11T17:08:43.339Z
---
Phase 5, Flow 1 (research-2026-11-11-uv-and-macos-app-install.md). The app checks a required minimum metab version (later the host-protocol version); below it, it starts no server and shows the exact upgrade command. Above it, features fall back as the identity route's 404 handling does. It rechecks the version when the runtime changes (uv tool upgrade) and offers to restart running servers. Parity: the version and its verdict come from metab, reachable from the CLI.
