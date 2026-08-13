---
type: is
id: is-01kzwkvevmw18dyvwjnxnyv58a
title: Reconcile the folder-view foundation
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-12-directory-file-type-summary.md
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
updated_at: 2026-08-13T04:12:20.820Z
closed_at: 2026-08-13T04:12:20.819Z
close_reason: Ported and reconciled the rollup, folder envelope/routing, SDK watcher, Treemap plugin, packaging, and focused foundation tests onto current main while preserving quick-file and current filter behavior.
---
Port the rollup, folder envelope/routing, SDK watcher, and Treemap prerequisites from feat/folder-treemap onto current main in the three slices under Baseline Reconciliation. Preserve newer shell behavior; do not land the hard-coded README tab, root README auto-navigation, singleton Markdown disposer, duplicate formatter, direct header refresher, or monolithic folder index as final code. Update root startup and foundation tests. Completion gate: focused Python/DOM tests plus formatting and type checks for touched files.
