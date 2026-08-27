---
type: is
id: is-01m0vscy963c6aphv6ga8wmxww
title: Implement a bounded virtual window for Git history rows
kind: task
status: in_progress
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-25-unbounded-virtualized-git-history.md
labels:
  - release:v0.9.0
dependencies:
  - type: blocks
    target: is-01m0vsd8dnak6hw2b87x5awch6
parent_id: is-01m0ghvrnps0hh3m8d28xvfn2j
created_at: 2026-08-25T06:23:23.429Z
updated_at: 2026-08-27T04:37:40.600Z
---
Render only a measured fixed-height window around the viewport, backed by a bounded decoded-page cache and page-boundary graph checkpoints. Add spacers and scroll-segment rebasing before the browser height clamp; preserve row identity, graph lanes, ref colors, focus, selection, hover detail, and commit routes through mount, eviction, replay, and remount. Give observers, requests, tooltips, and listeners disposal paths and assert structural resource bounds without timing thresholds.

## Notes

Started after mb-abu2 completed at green PR #86 checkpoint 5b3173b. Implement the measured page cache and virtual row window as an isolated browser checkpoint, preserving selection and graph context within the frozen budgets before Phase 4 integration.
