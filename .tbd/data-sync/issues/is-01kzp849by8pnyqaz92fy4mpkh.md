---
type: is
id: is-01kzp849by8pnyqaz92fy4mpkh
title: Rebase folder-treemap branch onto the core chip family
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/done/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T16:29:40.093Z
updated_at: 2026-11-04T16:59:26.272Z
closed_at: 2026-11-01T16:21:20.196Z
close_reason: "PR #23 closed; the treemap landed in bcd1e301, and no .tm-seg or filter_state.js remains in src on main."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: f2431b34-4d34-4b94-91c6-007fb143ebfb
    linked_at: 2026-08-16T08:05:43.400Z
---
PR 23 drops its private .tm-seg/.tm-check/.filter-chip and filter_state.js in favour of the core family and shared state. Its current+ageWindow pair collapses to recency, and its ignored three-state to showIgnored. Toolbar keeps its view-local encodings (Metric, Grouping, Color, Depth).
