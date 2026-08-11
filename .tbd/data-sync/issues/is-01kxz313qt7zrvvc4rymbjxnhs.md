---
type: is
id: is-01kxz313qt7zrvvc4rymbjxnhs
title: "P3: budgets, design review, and docs"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:22:19.386Z
updated_at: 2026-07-23T22:14:31.910Z
closed_at: 2026-07-23T22:14:31.909Z
close_reason: "All three items done: (1) integration test test_rollup_reflects_real_fs_mutation_through_fs_change covers real mutation -> watcher -> fs.change (with root-scope ancestor upserts) -> rollup refresh, both add and delete; (2) .tm-viewport height now measured at mount/window-resize (clamped 280-900px, calc fallback retained, dispose detaches listener), vm-tested; (3) design-review checklist run via browser probe in both themes and both color modes: age text ramp darkened to clear WCAG AA on all washes and given its missing dark variants, two-tone focus ring, sub-label opacity fade, print hides toolbar, reduced motion verified, folder-header summary gap fixed. make verify green; 14/14 live regression checks pass."
---
Remaining validation scope after the spike: run the design-system review checklist fully (print output, reduced motion, a11y audit at contrast level; light/dark screenshots done), add one automated integration test from a real filesystem mutation through fs.change to a rollup refresh, and revisit the .tm-viewport fixed-height sizing (currently calc(100vh - 240px)) against the one-scroll-owner rule. Budgets are recorded in test output (layout ~3ms/800 cells; rollup <150ms budget met); docs updates landed (plugins.md, design-system.md, architecture.md).
