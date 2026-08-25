---
type: is
id: is-01m0vmz928cewndbdk6gnhbgqz
title: Preserve v0.7 tally responsiveness through provider extraction
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0tytbmjsb46bnmh5134r5tg
created_at: 2026-08-25T05:06:01.415Z
updated_at: 2026-08-25T05:08:43.715Z
closed_at: 2026-08-25T05:08:43.712Z
close_reason: "Rebased PR #74 onto origin/main c7dcb14 and preserved both v0.7 responsiveness invariants in PythonInventoryHandle: navigation tally freshness uses a nonblocking lock attempt, and the measured cooperative yield runs inside _compute_navigation_tallies. Updated the upstream test to use PythonInventoryHandle directly, without restoring InventoryIndex. Focused overlap suite: 79 passed. Full make verify: 1,601 pytest tests and 48 golden scenarios passed, with lint, types, audits, build, and distribution checks green. Implemented in 1e0f9b5."
resolution: null
duplicate_of: null
---
Rebasing PR #74 onto origin/main c7dcb14 exposed two integration regressions at exact rebased head 4d46c02: navigation_tallies_fresh_within blocked the request loop on _navigation_tally_lock, and the new upstream cooperative-yield test referenced the removed InventoryIndex alias. Port the upstream nonblocking cache probe and measured tally-yield loop into PythonInventoryHandle, keep the direct python_inventory.py name with no compatibility alias, run the focused overlap suite and make verify, then commit and push.
