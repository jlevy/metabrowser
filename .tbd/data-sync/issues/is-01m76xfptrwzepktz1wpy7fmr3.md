---
type: is
id: is-01m76xfptrwzepktz1wpy7fmr3
title: "ExecutableTrust: trust write access by the admin group"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76xfmqcnsxjs3e6sw99a1h5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T03:40:38.101Z
updated_at: 2026-11-12T03:40:43.204Z
---
Standard Homebrew installs (/opt/homebrew/bin, /opt/homebrew/Cellar) are group-writable by admin, so the strict rule refuses a Homebrew uv (and would refuse a Homebrew metab). Members of admin can already become root, so allowing group write when the group is admin (gid 80) adds no real exposure; other groups and world-writable stay refused. Apply in ExecutableTrust with tests.
