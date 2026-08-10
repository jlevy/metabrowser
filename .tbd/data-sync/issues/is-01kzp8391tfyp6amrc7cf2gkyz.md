---
type: is
id: is-01kzp8391tfyp6amrc7cf2gkyz
title: Tracked-versus-ignored nav tally
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
  - backend
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:07.001Z
updated_at: 2026-08-10T16:29:19.942Z
closed_at: 2026-08-10T16:29:19.941Z
close_reason: Implemented on feat/nav-filter-controls; make verify green at 813 tests.
---
InventoryIndex.root_summary() plus the /api/tree summary field and the split nav header. Cannot be summed from top-level children because ignored files nested under tracked directories would count as tracked. Covered by tests/test_inventory_root_summary.py.
