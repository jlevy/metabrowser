---
type: is
id: is-01kxz313qt7zrvvc4rymbjxnhs
title: "P3: budgets, design review, and docs"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:22:19.386Z
updated_at: 2026-07-20T07:30:37.581Z
---
Remaining validation scope after the spike: run the design-system review checklist fully (print output, reduced motion, a11y audit at contrast level; light/dark screenshots done), add one automated integration test from a real filesystem mutation through fs.change to a rollup refresh, and revisit the .tm-viewport fixed-height sizing (currently calc(100vh - 240px)) against the one-scroll-owner rule. Budgets are recorded in test output (layout ~3ms/800 cells; rollup <150ms budget met); docs updates landed (plugins.md, design-system.md, architecture.md).
