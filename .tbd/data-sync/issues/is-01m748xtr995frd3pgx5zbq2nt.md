---
type: is
id: is-01m748xtr995frd3pgx5zbq2nt
title: Health-check servers before attaching; send stderr straight to the log
kind: task
status: in_progress
priority: 2
version: 4
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
created_at: 2026-11-11T03:02:51.912Z
updated_at: 2026-11-12T00:37:52.500Z
started_at: 2026-11-12T00:37:52.499Z
---
Phase 2. A health check with a deadline before a window attaches (a live pid is not enough), and the server's stderr written directly to its log file so a stalled app cannot block it through a full pipe; stdout stays a pipe for the Serving line and later the ready line.
