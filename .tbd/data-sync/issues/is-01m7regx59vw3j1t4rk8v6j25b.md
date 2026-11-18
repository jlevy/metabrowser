---
type: is
id: is-01m7regx59vw3j1t4rk8v6j25b
title: "macOS app: rename the folder session's window-named page events"
kind: task
status: open
priority: 4
version: 1
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
labels: []
dependencies: []
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
created_at: 2026-11-18T23:05:28.489Z
updated_at: 2026-11-18T23:05:28.489Z
---
Deferred from Review A, suggestion A8, on jlevy/metabrowser#566. Since FolderPage split from BrowserWindowController, FolderSession counts pages, not windows, but several names still say "window":
- FolderSession.onAllWindowsClosed fires when the last page closes (FolderSession.pageClosed). Suggested: onAllPagesClosed.
- FolderSession.onWindowShown, FolderWindowState (ShellCore/Web/PageReload.swift, used by PageReload and PageMenu and their tests), and RestartWait's docs (ShellCore/Folders/RestartWait.swift) keep window names.

In #566 alone the two mean the same thing. From #568 on they differ: a folder in the background has a page and no window, and the last page closing, not the last window, stops the server. The rename was not made in #566 because it reaches files outside that layer (AppDelegate.swift, ShellCore and its tests) that the layers above were being edited in at the time. Do it in one commit once the stack has merged, or in #568 if that layer is still open: rename, update doc comments, and check arch-macos-app.md for the old names.
