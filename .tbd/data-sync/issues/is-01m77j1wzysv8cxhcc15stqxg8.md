---
type: is
id: is-01m77j1wzysv8cxhcc15stqxg8
title: "CI gates: the Apple git shim test is macOS-tier, and no test looks a tool up itself (#366 CI)"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T09:40:05.756Z
updated_at: 2026-11-12T09:50:05.356Z
started_at: 2026-11-12T09:40:18.119Z
closed_at: 2026-11-12T09:50:05.355Z
close_reason: Fixed in a868e38e on claude/cli-exit-on-eof (#366 CI run 43191637069).
resolution: null
duplicate_of: null
---
CI run 43191637069 on #366: strict skips refused the shim test's skip, and test_no_test_module_looks_a_tool_up_itself found which() calls in test_git_process_group.py.
