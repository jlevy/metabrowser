---
type: is
id: is-01m0t6yygjga3yzzgsbnkk064x
title: Stabilize SIGINT teardown during provider discovery
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - stability
dependencies: []
parent_id: is-01m0t5yhbk3cds1j6x33pvaf26
created_at: 2026-08-24T15:41:56.113Z
updated_at: 2026-08-24T15:57:07.296Z
closed_at: 2026-08-24T15:57:07.295Z
close_reason: Two SIGTERM exits occurred only while a separate worktree ran its own full verification concurrently. No cancellation defect reproduced in more than 90 focused repetitions, eight full CLI-module runs, or an isolated make verify; all diagnostic edits were removed.
resolution: null
duplicate_of: null
---
Investigate the intermittent failure of tests/test_cli_main.py::test_console_entry_point_interrupts_background_filesystem_work after the rebase. Reproduce the -15 versus 130 exit race, audit server and InventoryRuntime/PythonInventoryHandle cancellation, fix the owning layer if real, and require repeated focused passes plus make verify.
