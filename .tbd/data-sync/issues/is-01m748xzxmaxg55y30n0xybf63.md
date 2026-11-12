---
type: is
id: is-01m748xzxmaxg55y30n0xybf63
title: macOS CI job for the app
kind: task
status: in_progress
priority: 3
version: 5
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
updated_at: 2026-11-12T00:19:08.763Z
started_at: 2026-11-12T00:19:08.753Z
---
Phase 5. Build and test apps/macos on a macOS runner, and later sign and notarize release builds from secrets in a temporary keychain.

## Notes

2026-11-11: The user granted adding this workflow for the v1 milestone: asked "Can the v1 work add a macOS CI workflow under .github/workflows?", they answered "Yes, add it". Scope: a macOS app workflow (build, test, ad hoc release rehearsal, check-dmg) and gating publish.yml to the Python package's v<version> release tags. Not a standing grant for other workflow changes.
