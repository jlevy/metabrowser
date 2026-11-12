---
type: is
id: is-01m748xzxmaxg55y30n0xybf63
title: macOS CI job for the app
kind: task
status: closed
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T03:02:57.202Z
updated_at: 2026-11-12T00:55:29.678Z
started_at: 2026-11-12T00:19:08.753Z
closed_at: 2026-11-12T00:55:29.662Z
close_reason: "Done on claude/macos-app-spike: .github/workflows/macos-app.yml (ec719287, uv checksum fixed in b0310862, macOS 26 only from bc6477a5) builds, tests (live suite guarded), and rehearses the release on macos-26 with Xcode 26.6; publish.yml runs only for v tags (7a27617e). First green run at bc6477a5. The signed release job stays mb-e9fm."
resolution: null
duplicate_of: null
---
Phase 5. Build and test apps/macos on a macOS runner, and later sign and notarize release builds from secrets in a temporary keychain.

## Notes

2026-11-11: The user granted adding this workflow for the v1 milestone: asked "Can the v1 work add a macOS CI workflow under .github/workflows?", they answered "Yes, add it". Scope: a macOS app workflow (build, test, ad hoc release rehearsal, check-dmg) and gating publish.yml to the Python package's v<version> release tags. Not a standing grant for other workflow changes.
