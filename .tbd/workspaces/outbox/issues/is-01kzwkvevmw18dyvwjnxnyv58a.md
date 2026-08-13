---
type: is
id: is-01kzwkvevmw18dyvwjnxnyv58a
title: Reconcile the folder-view foundation
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - implementation
dependencies:
  - type: blocks
    target: is-01kzwkvtqqrtdyafd6vkspsm9b
  - type: blocks
    target: is-01kzwkw4ppv374t7ae849n5yvx
  - type: blocks
    target: is-01kzwkwgrrdww56y99n5gsz65c
parent_id: is-01kzwg302q9172bvjc543whcte
created_at: 2026-08-13T03:50:00.307Z
updated_at: 2026-08-13T06:16:35.791Z
closed_at: 2026-08-13T06:16:35.790Z
close_reason: Implemented and validated on codex/folder-overview-implementation; focused coverage and make verify pass.
---
Port the rollup, folder envelope/routing, SDK watcher, and Treemap prerequisites from feat/folder-treemap onto current main in the three slices under Baseline Reconciliation. Preserve newer shell behavior; do not land the hard-coded README tab, root README auto-navigation, singleton Markdown disposer, duplicate formatter, direct header refresher, or monolithic folder index as final code. Update root startup and foundation tests. Completion gate: focused Python/DOM tests plus formatting and type checks for touched files.
