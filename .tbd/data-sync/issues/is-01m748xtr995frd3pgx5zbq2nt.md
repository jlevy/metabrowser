---
type: is
id: is-01m748xtr995frd3pgx5zbq2nt
title: Health-check servers before attaching; send stderr straight to the log
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:51.912Z
updated_at: 2026-11-11T03:02:51.912Z
---
Phase 2. A health check with a deadline before a window attaches (a live pid is not enough), and the server's stderr written directly to its log file so a stalled app cannot block it through a full pipe; stdout stays a pipe for the Serving line and later the ready line.
