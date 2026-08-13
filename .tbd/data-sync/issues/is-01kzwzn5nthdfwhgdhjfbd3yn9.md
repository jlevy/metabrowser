---
type: is
id: is-01kzwzn5nthdfwhgdhjfbd3yn9
title: Batch recursive tree collapse synchronization
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T07:16:17.209Z
updated_at: 2026-08-13T07:23:50.184Z
closed_at: 2026-08-13T07:23:50.183Z
close_reason: Batched recursive tree collapse synchronization into one final pass, with regression coverage.
---
Bugbot review thread PRRT_kwDOTX174c6Y2CWp found that recursive Shift+click collapse calls full tree synchronization once per descendant through setFolderExpanded. Add an explicit batch path and synchronize once after the recursive operation.
