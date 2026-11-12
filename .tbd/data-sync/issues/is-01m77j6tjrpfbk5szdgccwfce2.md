---
type: is
id: is-01m77j6tjrpfbk5szdgccwfce2
title: The shim lookup asks again for the system selection and keeps no failure (#366 review D2)
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
created_at: 2026-11-12T09:42:47.126Z
updated_at: 2026-11-12T09:50:06.450Z
started_at: 2026-11-12T09:42:58.309Z
closed_at: 2026-11-12T09:50:06.448Z
close_reason: Fixed in 28d4ceed on claude/cli-exit-on-eof (#366 review D2).
resolution: null
duplicate_of: null
---
Review D on #366, D2: the cache keyed by (name, developer_dir) froze the system selection when DEVELOPER_DIR was absent and kept failed lookups forever.
