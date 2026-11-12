---
type: is
id: is-01m75r1y7vycw6kpfkcegtp4zh
title: Clean-account matrix for both setup flows
kind: task
status: open
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1wvvdpmyaeqcp4my33zb
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:29.626Z
updated_at: 2026-11-12T00:43:32.483Z
---
Phase 5, measured (research-2026-11-11-uv-and-macos-app-install.md). Flow 1 (uv tool install, then the DMG or cask) and Flow 2 (the app first, no metab) on macOS 15 and 26, admin and standard accounts, with and without the Command Line Tools: Gatekeeper's first-launch prompt, no translocation after moving to Applications, discovery from a Finder launch, the version policy, uv#14893's developer-tools dialog, Spotlight and Apps view visibility, and whether privacy grants survive an upgrade.

## Notes

2026-11-11 (review A3 on #357): v1's end-to-end check (mb-hwxu) covers both flows on the build Mac with fresh settings; this matrix (other macOS versions, standard accounts, no Command Line Tools) and the Developer ID and Gatekeeper checks (mb-e9fm) stay outside v1 as its named limitation.

2026-11-11, the user: "we do not need to support older macOS let's pick a reasonable minimal version that lets us keep the app very new and modern." The app now requires macOS 26 and Swift 6.3 (bc6477a5 on claude/macos-app-spike), so this matrix drops macOS 15: macOS 26 and the current release, admin and standard accounts, with and without the Command Line Tools.
