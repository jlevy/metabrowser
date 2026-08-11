---
type: is
id: is-01kzp838sjwj9g9ptz1q7420wc
title: Retire the Recent tab; recency reads /api/recent
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:06.737Z
updated_at: 2026-08-10T16:29:19.737Z
closed_at: 2026-08-10T16:29:19.736Z
close_reason: Implemented on feat/nav-filter-controls; make verify green at 813 tests.
---
A recency window swaps the Files tree's data source to /api/recent, which scans the whole index rather than loaded subtrees. That is the one thing the tab did that a DOM walk cannot, so the tab retires without narrowing what it could answer.
