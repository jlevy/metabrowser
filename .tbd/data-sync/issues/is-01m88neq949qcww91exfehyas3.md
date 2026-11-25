---
type: is
id: is-01m88neq949qcww91exfehyas3
title: "macOS app: folders always open in their own window, never as tabs"
kind: task
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-25T06:14:27.868Z
updated_at: 2026-11-25T06:16:13.042Z
started_at: 2026-11-25T06:16:13.004Z
---
The user: "let's just remove this option of having folders open as tabs altogether." They never asked for tabs, and the dev build's saved 'Open folders in: Tabs' made folders keep opening as tabs. Remove the Settings 'Open folders in' choice (System / Tabs / Windows) and its saved newFolderPlacement value, stop following macOS's 'Prefer tabs' preference, and make every way a folder opens (File > Open, open -a, metab --present, Dock drop, a GitHub mirror opened from its checkout's window, Command-click on a same-server link, relaunch) give a window of its own; folder windows take no tabs at all, so Merge All Windows and tab dragging cannot make one. Remove what only tabs needed (placement, tab moves, tab-group restore, and the background-tab discard policy if nothing else uses it). Done when no path opens a tab, tests pin each path, and the docs, QA hand checks and a changelog fragment say so.
