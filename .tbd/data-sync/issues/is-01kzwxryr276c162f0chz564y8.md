---
type: is
id: is-01kzwxryr276c162f0chz564y8
title: Prevent live tree inserts from duplicating paged rows
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T06:43:24.026Z
updated_at: 2026-08-13T07:01:30.600Z
closed_at: 2026-08-13T07:01:30.599Z
close_reason: Fixed deferred-page reconciliation and retained focus-repair snapshots across animated live removals. The 213-entry real-browser regression now mounts every path once, updates sentinel totals on pending removals, and repairs focus after mounted removals.
---
Real-browser validation with 213 files showed inventory events inserting rows beyond the mounted 200-row page while the pagination sentinel remained. Activating Show more then mounted the same rows again. Keep live insertion, page metadata, and focus repair coherent so each path renders once before and after pagination.
