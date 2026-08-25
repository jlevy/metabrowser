---
type: is
id: is-01m0vmz928cewndbdk6gnhbgqz
title: Preserve v0.7 tally responsiveness through provider extraction
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0tytbmjsb46bnmh5134r5tg
created_at: 2026-08-25T05:06:01.415Z
updated_at: 2026-08-25T05:18:23.998Z
closed_at: 2026-08-25T05:18:23.997Z
close_reason: CI rerun 32811814043 completed green on Python 3.12, 3.13, and 3.14, plus lint and distribution. The original 3.12-only 55ms event-loop sentinel miss did not reproduce; Python 3.13/3.14 had only been canceled by fail-fast. Ten consecutive local focused runs measured 4.9-7.6ms. Classified as shared-runner timing noise with exact evidence; no production or test threshold change was warranted.
resolution: null
duplicate_of: null
---
Rebasing PR #74 onto origin/main c7dcb14 exposed two integration regressions at exact rebased head 4d46c02: navigation_tallies_fresh_within blocked the request loop on _navigation_tally_lock, and the new upstream cooperative-yield test referenced the removed InventoryIndex alias. Port the upstream nonblocking cache probe and measured tally-yield loop into PythonInventoryHandle, keep the direct python_inventory.py name with no compatibility alias, run the focused overlap suite and make verify, then commit and push.

## Notes

Exact-head CI run 32811814043: lint and distribution passed; Python 3.12 ran all 1,601 tests and failed only the pre-existing active-tracker stall sentinel at 55.0ms against its 50ms limit. Python 3.13/3.14 were canceled by fail-fast, not independent failures. The focused test passes ten consecutive local runs at 4.9-7.6ms. Rerun failed jobs before changing code to distinguish shared-runner scheduling noise from a reproducible integration regression.
