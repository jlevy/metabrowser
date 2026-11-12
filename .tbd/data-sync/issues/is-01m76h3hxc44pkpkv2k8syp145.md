---
type: is
id: is-01m76h3hxc44pkpkv2k8syp145
title: Rebuild the v1 app and check it end to end
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T00:04:16.939Z
updated_at: 2026-11-12T00:04:23.313Z
---
After the review is addressed: rebuild the dev and release-rehearsal bundles and DMGs, relaunch the dev app on real folders, and run every manual check the implementation beads recorded (first run without metab, an old metab, a launch from the DMG, opening a file, recents, tabs, session restore, crash recovery), recording results in the PR.
