---
type: is
id: is-01m76cd1ysrge9arg7a773j3ff
title: Dock and File menu recents through NSDocumentController
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
created_at: 2026-11-11T22:42:05.400Z
updated_at: 2026-11-11T22:42:07.124Z
---
Register opened folders with NSDocumentController so the Dock menu and File > Open Recent list them, as macOS keeps that list (a platform exemption from CLI parity, recorded in the topology brief after review A on #352).
