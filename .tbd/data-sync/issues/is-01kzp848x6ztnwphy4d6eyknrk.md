---
type: is
id: is-01kzp848x6ztnwphy4d6eyknrk
title: No keyboard-traversal test for the extension dropdown
kind: task
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - testing
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:39.622Z
updated_at: 2026-08-10T18:19:50.488Z
closed_at: 2026-08-10T18:19:50.487Z
close_reason: Added arrow-key row traversal to the dropdown (the gap was the behavior, not only its test) plus coverage in tests/dom/filter_controls_behavior.js and tests/test_browser_filter_ui.py.
---
Chip groups have arrow-key coverage; the dropdown does not. Escape and outside-click dismissal are wired and follow the design system rule but were verified by reading, not by driving them. Needs a DOM-level test over menu row traversal.
