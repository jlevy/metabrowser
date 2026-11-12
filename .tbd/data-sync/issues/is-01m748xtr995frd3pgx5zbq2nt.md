---
type: is
id: is-01m748xtr995frd3pgx5zbq2nt
title: Health-check servers before attaching; send stderr straight to the log
kind: task
status: closed
priority: 2
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
created_at: 2026-11-11T03:02:51.912Z
updated_at: 2026-11-12T01:48:49.544Z
started_at: 2026-11-12T00:37:52.499Z
closed_at: 2026-11-12T01:48:49.543Z
close_reason: "Done on claude/v1-robustness: stderr goes straight to the server log and the error view reads this run's part of the log (1d91e7c5); ServerSupervisor.checkHealth with a 5 s deadline, measured and recorded beside the constant, before a window joins a running server: Command-click, a folder brought back, show(page), and a revived discarded tab (58b743c2, 1683e3ae). Manual checks in apps/macos/README.md, Checking by Hand. Pushed at 8f45a32e."
resolution: null
duplicate_of: null
---
Phase 2. A health check with a deadline before a window attaches (a live pid is not enough), and the server's stderr written directly to its log file so a stalled app cannot block it through a full pipe; stdout stays a pipe for the Serving line and later the ready line.
