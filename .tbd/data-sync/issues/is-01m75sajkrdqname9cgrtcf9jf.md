---
type: is
id: is-01m75sajkrdqname9cgrtcf9jf
title: "First run without metab: copyable commands for the missing steps, then continue"
kind: feature
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m75sak36bbvrc702gp5xjq1s
  - type: blocks
    target: is-01m75r1y7vycw6kpfkcegtp4zh
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
  - type: blocks
    target: is-01m75sakkrx1z0r515j70xe265
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-11T17:08:41.207Z
updated_at: 2026-11-12T01:40:39.518Z
started_at: 2026-11-12T00:38:22.793Z
closed_at: 2026-11-12T01:40:39.517Z
close_reason: SetupGuide shows only the missing steps (uv installer or brew, uv tool install, --reinstall, floor upgrade), uv tool dir --bin, watch continues by itself, update-shell hint. 4242b0c90; checked live with scripts/check-setup-flows.sh no-metab (5cc43107).
resolution: null
duplicate_of: null
---
Phase 5, Flow 2 option (i) (research-2026-11-11-uv-and-macos-app-install.md). When discovery finds no metab, the app detects whether uv is present and shows only the missing commands (installing uv, uv tool install metabrowser), watches uv's tool bin directory, and opens the pending folder by itself when metab appears.
