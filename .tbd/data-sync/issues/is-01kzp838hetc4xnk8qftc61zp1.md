---
type: is
id: is-01kzp838hetc4xnk8qftc61zp1
title: Apply filters to the tree as a decoration layer
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:06.477Z
updated_at: 2026-08-10T16:29:19.543Z
closed_at: 2026-08-10T16:29:19.542Z
close_reason: Implemented on feat/nav-filter-controls; make verify green at 813 tests.
---
Prune non-matching rows, retain folders with no loaded match, propagate a hidden folder's verdict to descendants, and render an unloaded-folders footer note. With no filters set the DOM is byte-identical to before.
