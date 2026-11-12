---
type: is
id: is-01m76h3hxc44pkpkv2k8syp145
title: Rebuild the v1 app and check it end to end
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T00:04:16.939Z
updated_at: 2026-11-12T00:14:00.711Z
---
After the review is addressed: rebuild the dev and release-rehearsal bundles and DMGs; with fresh app settings on the build Mac, run Flow 1 (uv tool install metabrowser, then the app from the DMG) and Flow 2 (the app with no metab, the copyable commands, continuing when metab appears), an old metab, a launch from the DMG, opening a file, recents, tabs, session restore, and crash recovery, plus every manual check the implementation beads recorded; record the results in the PR. Not covered, and named as v1's limitation: other macOS versions, standard accounts, and no Command Line Tools (mb-5fp7), and Developer ID and Gatekeeper checks (mb-e9fm).
