---
type: is
id: is-01m0t8bsr9gv90q773ajk4ynm6
title: Audit browser startup and asset-loading invariants from PR 73
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - browser
  - performance
dependencies:
  - type: blocks
    target: is-01m0t8c0dr9dc0xkz1kvw6dya1
parent_id: is-01m0t88jfkvafypd9h2sgvfz6p
created_at: 2026-08-24T16:06:25.800Z
updated_at: 2026-08-24T16:50:43.467Z
closed_at: 2026-08-24T16:50:43.466Z
close_reason: All landed browser startup and asset-loading invariants survive the provider refactor and pass focused plus full verification.
resolution: null
duplicate_of: null
---
Trace PR 73 tree-first fetch priority, inline-tree reconciliation, live delivery slicing, deferred shell tools, on-demand plugin assets, catalog readiness, SDK naming, and styling behavior through the provider branch. Prove the final browser path retains each invariant.

## Notes

Production app.js, plugin-sdk.js, and styles.css remain behaviorally identical to landed PR 73 except provider terminology comments. Tree-first load ordering, inline reconciliation, deferred shell tools, on-demand plugin assets, exact preload accounting, catalog readiness, and markdown asset awaiting retain their landed coverage. The 319-test focused subset and full make verify pass.
