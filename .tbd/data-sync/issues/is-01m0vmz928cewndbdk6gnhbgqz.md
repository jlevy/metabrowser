---
type: is
id: is-01m0vmz928cewndbdk6gnhbgqz
title: Preserve v0.7 tally responsiveness through provider extraction
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0tytbmjsb46bnmh5134r5tg
created_at: 2026-08-25T05:06:01.415Z
updated_at: 2026-08-25T05:06:01.415Z
---
Rebasing PR #74 onto origin/main c7dcb14 exposed two integration regressions at exact rebased head 4d46c02: navigation_tallies_fresh_within blocked the request loop on _navigation_tally_lock, and the new upstream cooperative-yield test referenced the removed InventoryIndex alias. Port the upstream nonblocking cache probe and measured tally-yield loop into PythonInventoryHandle, keep the direct python_inventory.py name with no compatibility alias, run the focused overlap suite and make verify, then commit and push.
