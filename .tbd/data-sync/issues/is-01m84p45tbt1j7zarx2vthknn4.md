---
type: is
id: is-01m84p45tbt1j7zarx2vthknn4
title: macOS title menu focuses or opens folders in separate windows
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-11-23T17:09:13.159Z
updated_at: 2026-11-23T17:54:15.353Z
closed_at: 2026-11-23T17:54:15.349Z
close_reason: Reviewed and merged in https://github.com/jlevy/metabrowser/pull/760 at 55e8365870f0fb0ff6b8d3985b0dedf54872ae0d. All 73 focused native tests, full make verify (45226019764), exact PR CI and macOS packaging, and exact post-merge main CI (45231004562) and macOS (45231003819) passed. The active development app was rebuilt, the saved window restored, and its server answered. The interactive click-through was interrupted by the desktop connection.
resolution: null
duplicate_of: null
---
For every Open or Recent target in the native title menu, focus its current window or show it in a separate new window. Preserve the source window and use the existing background page and server where available. Cover native tab preferences and keep the keyboard Switch Folder panel behavior.
