---
type: is
id: is-01m78fd7rt1t7eww5sqks2xgbn
title: Install review build 2692 (ae5d3ed) to /Applications
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m76h3hxc44pkpkv2k8syp145
created_at: 2026-11-12T18:13:05.945Z
updated_at: 2026-11-12T22:37:28.929Z
---
Built from the stack top 41858a3d plus #367, with the mb-sugi fix. Waits for the running Metabrowser to quit; install with ditto, verify codesign and MetabrowserSourceCommit, then relaunch and check the windows restore with the review build's metab.

## Notes

2026-11-12: superseded 2684 with 2692 (ae5d3ed): #384's head d9b4e07f (stack top with the mb-sugi fix, the Metabrowser folders, the title-bar logo, and larger windows) plus #367 and #385 (branch colors, badge centering). Install with the scratchpad's install-and-move-session.sh once Metabrowser is quit: it copies session.json from the old bundle-identifier folder to Application Support/Metabrowser, relaunches, and checks logs land in ~/Library/Logs/Metabrowser.
