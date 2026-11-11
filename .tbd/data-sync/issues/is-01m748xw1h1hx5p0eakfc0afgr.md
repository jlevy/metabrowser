---
type: is
id: is-01m748xw1h1hx5p0eakfc0afgr
title: "Control verbs: identity, present, clients, close, on an owner-only socket"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xwf9kpmst8t6jk2n95hj
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:53.232Z
updated_at: 2026-11-11T03:03:02.389Z
---
Phase 3. Extend /api/identity with pid, boot id, and version; add present (pushes a navigate event to the root's most recently visible page), clients, and close. Only these verbs are served on the owner-only Unix socket (path within 104 bytes); content routes stay on loopback behind the page token. Goldens for each.
