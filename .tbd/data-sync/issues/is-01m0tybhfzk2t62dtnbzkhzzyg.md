---
type: is
id: is-01m0tybhfzk2t62dtnbzkhzzyg
title: Preserve deterministic order when loading multiple plugins for one kind
kind: bug
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
  - type: blocks
    target: is-01m0vdm7d6j696m0acyqxsq215
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
hold: null
hold_until: null
created_at: 2026-08-24T22:30:46.014Z
updated_at: 2026-08-25T03:21:24.878Z
started_at: 2026-08-25T03:19:10.038Z
closed_at: 2026-08-25T03:21:24.877Z
close_reason: Load complete same-kind plugin descriptors sequentially in discovery order; delayed-module behavior proves the later manifest wins deterministically; make verify passes.
resolution: null
duplicate_of: null
---
Release-readiness finding on main c123ae6. loadPluginsForKind starts all descriptors with Promise.all, so network and module completion order decides which registerView call wins when two plugins register the same kind/view. Add a delayed two-plugin behavioral test that fails on c123ae6, then load descriptors sequentially in the server's stable discovery order. Preserve per-plugin asset ordering, in-flight deduplication, retry behavior, and the installed-browser startup budgets.
