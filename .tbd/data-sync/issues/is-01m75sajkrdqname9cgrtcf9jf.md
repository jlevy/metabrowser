---
type: is
id: is-01m75sajkrdqname9cgrtcf9jf
title: "First run without metab: copyable commands for the missing steps, then continue"
kind: feature
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
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
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T17:08:41.207Z
updated_at: 2026-11-12T00:04:19.590Z
---
Phase 5, Flow 2 option (i) (research-2026-11-11-uv-and-macos-app-install.md). When discovery finds no metab, the app detects whether uv is present and shows only the missing commands (installing uv, uv tool install metabrowser), watches uv's tool bin directory, and opens the pending folder by itself when metab appears.
