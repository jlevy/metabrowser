---
type: is
id: is-01m75r1xshbawtvcvdw389y3hq
title: Find the app by bundle id from metab
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1wvvdpmyaeqcp4my33zb
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:29.169Z
updated_at: 2026-11-11T16:46:31.136Z
---
Phase 5. A read-only LaunchServices lookup by bundle id (measured about 0.09 s), filtered to Applications folders because it also returns build-folder copies; shared with the agent front door (mb-idri) and the install mode (research-2026-11-11-uv-and-macos-app-install.md).
