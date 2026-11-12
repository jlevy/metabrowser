---
type: is
id: is-01m76cd1ysrge9arg7a773j3ff
title: "Recents owned by macOS: NSDocumentController replaces the app's list"
kind: task
status: closed
priority: 2
version: 7
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
created_at: 2026-11-11T22:42:05.400Z
updated_at: 2026-11-12T01:25:37.934Z
started_at: 2026-11-12T00:37:59.169Z
closed_at: 2026-11-12T01:25:37.933Z
close_reason: Opened folders are registered with NSDocumentController; File > Open Recent draws recentDocumentURLs and Clear Menu clears them; RecentFolderStore and RecentFolders are removed. Commit 3e566b3e. Verified with a scratch bundle on macOS 26.5 that folders are recorded and persist; the Dock menu's list is a manual check in apps/macos/README.md.
resolution: null
duplicate_of: null
---
v1 milestone (review A2 on jlevy/metabrowser#357). Opened folders are registered with NSDocumentController, and that OS-owned list is the only recents the app keeps: it backs the Dock menu, File > Open Recent, and any recent list in the app's own windows. The app's RecentFolderStore (an app-defined ordered list in UserDefaults) is removed, so no app-owned membership or order remains, which is the platform exemption the topology brief records. Recent and added roots persisted in metab, with a route and goldens, stay in Phase 4 (mb-a5ru), and the quick switcher over them stays mb-9lf4.
