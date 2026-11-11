---
type: is
id: is-01m748y280ktz4beqt4ed9bm3c
title: replace_root keeps about 85 MB more than closing a runtime
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:59.583Z
updated_at: 2026-11-11T03:02:59.583Z
---
Phase 6. In one process, replace_root from a 387k-entry root to a 75-entry root left the footprint at 172-173 MB, against 86-87 MB after closing a separate runtime (research-2026-11-10 eviction probe). Matters to mb-vmzy before any in-process root switching.
