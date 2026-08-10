---
type: is
id: is-01kzp837rxqpvw3f8ryxhbtnat
title: FilterState module and mb.prefs/mb.filters SDK surface
kind: feature
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:05.692Z
updated_at: 2026-08-10T16:29:18.943Z
closed_at: 2026-08-10T16:29:18.942Z
close_reason: Implemented on feat/nav-filter-controls; make verify green at 813 tests.
---
static/filter_state.js under the strict tsconfig gate: recency/types/size/showIgnored, cookie persistence via mb.prefs, change events, activeCount, shared predicates. Covered by tests/dom/filter_state_behavior.js.
