---
type: is
id: is-01m77j4ds3w4e17nh62q2nbtfx
title: An absolute launch's identity needs no current directory (#366 review D1)
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:41:28.482Z
updated_at: 2026-11-12T09:50:05.903Z
started_at: 2026-11-12T09:41:41.436Z
closed_at: 2026-11-12T09:50:05.901Z
close_reason: Fixed in 470e93c2 on claude/cli-exit-on-eof (#366 review D1).
resolution: null
duplicate_of: null
---
Review D on #366, D1: _launched_files called os.getcwd() up front, so a removed current directory failed even an absolute launch, including gh's ordinary _run.
