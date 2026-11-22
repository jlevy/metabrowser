---
type: is
id: is-01m748xzfj0nvstrsj9766877c
title: Developer ID signing, notarization, a DMG, and a Homebrew cask
kind: feature
status: open
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:56.753Z
updated_at: 2026-11-22T21:10:09.765Z
started_at: 2026-11-11T03:08:02.538Z
---
Phase 5. The pipeline is on main (jlevy/metabrowser#341): make macos-release signs inside out with the hardened runtime and a secure timestamp, notarizes with notarytool, staples the app and the DMG, checks them, and renders the cask from apps/macos/packaging/metabrowser-app.rb.template; macos-app.yml rehearses it with an ad hoc signature. Remaining, all waiting on the owner: a Developer ID identity and notary credentials on the build Mac, the first signed and notarized release, a CI release job on macos-v* tags (needs the user's approval and secrets), publishing the draft GitHub release, and the cask in a personal tap.

## Notes

Implemented on claude/macos-release-build (360468ee): make macos-release signs inside out with the hardened runtime and a secure timestamp, notarizes and staples the app and the DMG, checks them, and renders build/metabrowser-app.rb from packaging/metabrowser-app.rb.template. Tested end to end ad hoc only; no Developer ID identity exists on the build Mac. Remaining: a first real signed and notarized release, the published icon committed, GitHub Release publishing (draft workflow in the handoff; publish.yml must skip macos-v* releases first), and the cask in a personal tap.

2026-11-11: Merged into claude/macos-app-spike and pushed to jlevy/metabrowser#341 at 21dae3c3 (not to be merged into main until the user says so).

2026-11-22: the signing, notarization and DMG part of this feature is now delivered by the release epic mb-wzsl. The Phase 1 tooling beads (mb-qu6j, mb-4hwg, mb-tfap, mb-xd4o, mb-u36j, mb-63cx) are closed, and the first signed build is mb-1d8p. What remains here is the Homebrew cask (mb-eoez) and CI signing (mb-mww5, mb-3ey5).
