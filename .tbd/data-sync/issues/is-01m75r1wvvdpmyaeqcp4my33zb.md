---
type: is
id: is-01m75r1wvvdpmyaeqcp4my33zb
title: metab installs, reports, and removes the native app
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:28.207Z
updated_at: 2026-11-11T16:46:28.207Z
---
Phase 5. Design (a) in research-2026-11-11-uv-and-macos-app-install.md: a metab mode fetches the notarized, stapled app ZIP from GitHub Releases; verifies the release checksum, a code requirement pinning the Developer ID anchor, Team ID, and release bundle id, and --check-notarization; never sets quarantine; stages a complete copy and renames it into /Applications when writable, else ~/Applications, never with sudo; refuses a second copy and leaves a cask-owned copy to Homebrew; writes a receipt outside the bundle. Under uvx it prints uv tool install metabrowser==<version> so the app has a persistent CLI. Parity: a status --json mode and an install --dry-run with goldens against fixture bundles and an injected verifier; mode names must not collide with metab TARGET.
