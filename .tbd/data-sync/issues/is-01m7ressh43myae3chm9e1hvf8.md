---
type: is
id: is-01m7ressh43myae3chm9e1hvf8
title: "Folder switching: the plan's app tests, live tests, and screenshot set"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
labels: []
dependencies: []
parent_id: is-01m7r5cmz107gb7jxq0y6pp7fe
created_at: 2026-11-18T23:10:19.683Z
updated_at: 2026-11-18T23:10:19.683Z
---
Deferred from Review A, finding A12 (Low), on jlevy/metabrowser#578 (View > Switch Folder... panel). The plan's Testing Strategy promises: app tests beside TabsTests (a switch keeps the same NSWindow, its frame, and its place in a tab group; a switch back to a live page loads nothing; a switch to a discarded page loads once; a window with a page sheet does not switch; closing a window closes only folders no other window shows); live tests against a real metab (switching between two folders and a repository, each server running once); and a macOS 26.5 screenshot set of the title, chevron, hover surface, and open menu in light and dark, key and not key. None exists yet. Until it does, the Switching Folders hand checks in docs/project/qa/qa-macos-app-hand-checks.md cover these paths by hand (mb-6ccy stays open until they have been run). The app tests need the app test target mb-q2hc adds; FolderPage makes a WKWebView, so they join webkit_suites in apps/macos/Makefile.
