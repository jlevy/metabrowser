---
type: is
id: is-01m75r1xat7yxdgbs3qp506bet
title: Publish the stapled app ZIP and a release manifest
kind: task
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1wvvdpmyaeqcp4my33zb
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:28.697Z
updated_at: 2026-11-11T17:08:46.728Z
---
Phase 5. Beside the DMG, the release pipeline publishes a stapled ZIP (keeps symlinks, needs no mount) and a manifest with version, host-protocol version, and SHA-256, for the metab install mode (research-2026-11-11-uv-and-macos-app-install.md). Relates to mb-e9fm.

## Notes

2026-11-11: Re-scoped by the revised research-2026-11-11-uv-and-macos-app-install.md to a later option, once both standard setup flows pass (mb-5fp7).
