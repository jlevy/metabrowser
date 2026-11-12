---
type: is
id: is-01m748xswj3y4wnc6bfb60kmp6
title: Lazy session restore
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:51.025Z
updated_at: 2026-11-12T01:25:38.602Z
started_at: 2026-11-12T00:37:59.903Z
closed_at: 2026-11-12T01:25:38.601Z
close_reason: "SessionStore saves windows and tabs atomically (0600 in 0700); RestoreQueue starts the front tab's server first, then the others one at a time, and defers protected locations (ProtectedLocations) until selected. Commits 40cfa893, 41618d0a. End to end: start order, a deferred /Volumes root never started, missing folders dropped. Starts are scheduled, not crawls: metab reports no walk end."
resolution: null
duplicate_of: null
---
Phase 2. Recreate the last session's tabs, start the front tab's server first, then the rest one at a time, and none in a TCC-protected location until its tab is selected. The launch gate becomes the crawl scheduler.
