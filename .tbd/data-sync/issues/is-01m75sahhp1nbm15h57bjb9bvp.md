---
type: is
id: is-01m75sahhp1nbm15h57bjb9bvp
title: App requires a compatible metab version and notices upgrades
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1y7vycw6kpfkcegtp4zh
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
  - type: blocks
    target: is-01m75sakkrx1z0r515j70xe265
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T17:08:40.117Z
updated_at: 2026-11-12T00:13:56.586Z
---
Phase 5, Flow 1 (research-2026-11-11-uv-and-macos-app-install.md). The app checks a required minimum metab version (later the host-protocol version); below it, it starts no server and shows the exact upgrade command. Above it, features fall back as the identity route's 404 handling does. It rechecks the version when the runtime changes (uv tool upgrade) and offers to restart running servers. Parity: the version and its verdict come from metab, reachable from the CLI.

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): the app offers to restart the servers it started from the old version; it cannot stop an upgrade run in Terminal from reaching them first (Where This Breaks in the setup brief).

2026-11-11, from review B on jlevy/metabrowser#352 (fixed in 5136540f): an upgrade the app runs waits the same way as Reinstall and Remove (mb-34oi).
