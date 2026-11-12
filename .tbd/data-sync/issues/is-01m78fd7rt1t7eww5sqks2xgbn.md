---
type: is
id: is-01m78fd7rt1t7eww5sqks2xgbn
title: Install review build 2684 (0ebec9d) to /Applications
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m76h3hxc44pkpkv2k8syp145
created_at: 2026-11-12T18:13:05.945Z
updated_at: 2026-11-12T18:13:05.945Z
---
Built from the stack top 41858a3d plus #367, with the mb-sugi fix. Waits for the running Metabrowser to quit; install with ditto, verify codesign and MetabrowserSourceCommit, then relaunch and check the windows restore with the review build's metab.
