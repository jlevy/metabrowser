---
type: is
id: is-01kzp849by8pnyqaz92fy4mpkh
title: Rebase folder-treemap branch onto the core chip family
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:40.093Z
updated_at: 2026-08-10T16:29:40.093Z
---
PR 23 drops its private .tm-seg/.tm-check/.filter-chip and filter_state.js in favour of the core family and shared state. Its current+ageWindow pair collapses to recency, and its ignored three-state to showIgnored. Toolbar keeps its view-local encodings (Metric, Grouping, Color, Depth).
