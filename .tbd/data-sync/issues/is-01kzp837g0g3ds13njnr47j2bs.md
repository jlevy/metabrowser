---
type: is
id: is-01kzp837g0g3ds13njnr47j2bs
title: Chip control family in core styles
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:05.408Z
updated_at: 2026-08-10T16:29:18.737Z
closed_at: 2026-08-10T16:29:18.736Z
close_reason: Implemented on feat/nav-filter-controls; make verify green at 813 tests.
---
Promote .chip, .chip-group[data-select=one|many], .chip-toggle, .chip-menu, .chip-badge, .chip-clear into core styles.css, replacing .recent-chip and giving the treemap branch's .tm-seg/.tm-check/.filter-chip a home. Single-select fills accent, multi-select neutral plus inset frame. Covered by tests/dom/filter_controls_behavior.js and tests/test_browser_filter_ui.py.
