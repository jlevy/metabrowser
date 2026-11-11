---
type: is
id: is-01m748xzfj0nvstrsj9766877c
title: Developer ID signing, notarization, a DMG, and a Homebrew cask
kind: feature
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:56.753Z
updated_at: 2026-11-11T03:42:28.120Z
started_at: 2026-11-11T03:08:02.538Z
---
Phase 5. Sign inside out with the hardened runtime and a secure timestamp, notarize with notarytool, staple the app and DMG, publish to GitHub Releases, and add a cask in a personal tap.

## Notes

Implemented on claude/macos-release-build (360468ee): make macos-release signs inside out with the hardened runtime and a secure timestamp, notarizes and staples the app and the DMG, checks them, and renders build/metabrowser-app.rb from packaging/metabrowser-app.rb.template. Tested end to end ad hoc only; no Developer ID identity exists on the build Mac. Remaining: a first real signed and notarized release, the published icon committed, GitHub Release publishing (draft workflow in the handoff; publish.yml must skip macos-v* releases first), and the cask in a personal tap.
