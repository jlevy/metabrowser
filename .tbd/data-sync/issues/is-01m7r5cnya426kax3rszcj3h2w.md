---
type: is
id: is-01m7r5cnya426kax3rszcj3h2w
title: Open folders and switching a window in place
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m7r5cpw7ydejcrrp3m5myfa5
  - type: blocks
    target: is-01m7r5cqbfnb75d2301fykkfxy
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
hold: null
hold_until: null
created_at: 2026-11-18T20:25:52.841Z
updated_at: 2026-11-19T01:31:42.088Z
started_at: 2026-11-18T21:06:49.154Z
closed_at: 2026-11-19T01:31:42.087Z
close_reason: Merged in stack 579 (jlevy/metabrowser#565-#578) as 74d8d61
resolution: null
duplicate_of: null
---
PR 2. ShellCore OpenFolders (shown/background, open order, last shown) and its transition table; switching a window's content page keeps the NSWindow, frame, Space, full screen, and tab-group place; File > Close Folder; TabDiscardPolicy ranks pages; background folders in SavedSession, restored without starting servers. See the spec's Open Folders section.
