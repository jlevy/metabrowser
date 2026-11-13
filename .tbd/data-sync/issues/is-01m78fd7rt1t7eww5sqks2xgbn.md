---
type: is
id: is-01m78fd7rt1t7eww5sqks2xgbn
title: Install review build 2704 (1f86a4c) to /Applications
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m76h3hxc44pkpkv2k8syp145
created_at: 2026-11-12T18:13:05.945Z
updated_at: 2026-11-13T00:37:22.528Z
---
Built from the stack top 41858a3d plus #367, with the mb-sugi fix. Waits for the running Metabrowser to quit; install with ditto, verify codesign and MetabrowserSourceCommit, then relaunch and check the windows restore with the review build's metab.

## Notes

2026-11-12: build 2704 (1f86a4c) supersedes 2692: #384's head d9b4e07f (stack top: the mb-sugi fix, the Metabrowser folders, the title-bar logo, larger windows) plus #367, #385 (branch colors, badge centering), and #386 (catalog refusals, the cache-clear route, commands in messages). Install with the scratchpad's install-and-move-session.sh once Metabrowser is quit: it copies session.json from the bundle-identifier folder to Application Support/Metabrowser, relaunches, and checks logs land in ~/Library/Logs/Metabrowser.
