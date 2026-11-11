---
type: is
id: is-01m748xswj3y4wnc6bfb60kmp6
title: Lazy session restore
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:51.025Z
updated_at: 2026-11-11T22:42:10.009Z
---
Phase 2. Recreate the last session's tabs, start the front tab's server first, then the rest one at a time, and none in a TCC-protected location until its tab is selected. The launch gate becomes the crawl scheduler.
