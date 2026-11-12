---
type: is
id: is-01m75saj4h7s3trg7kt812fbya
title: Flag disk-image and translocated launches with a Move to Applications notice
kind: task
status: closed
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
created_at: 2026-11-11T17:08:40.720Z
updated_at: 2026-11-12T01:40:39.858Z
started_at: 2026-11-12T00:38:23.555Z
closed_at: 2026-11-12T01:40:39.857Z
close_reason: LaunchLocation (path /AppTranslocation/, statfs read-only volume) and a launch notice; the move is the user's in Finder. 8c316eac; disk-image case checked live with scripts/check-setup-flows.sh disk-image; translocation tested on the path only.
resolution: null
duplicate_of: null
---
Phase 5, Flow 1 (research-2026-11-11-uv-and-macos-app-install.md). A copy run from the DMG, or translocated, gets a first-run notice offering to move it to Applications, since a translocated app cannot update itself.
