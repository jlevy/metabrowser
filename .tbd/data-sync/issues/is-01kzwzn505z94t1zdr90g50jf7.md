---
type: is
id: is-01kzwzn505z94t1zdr90g50jf7
title: Discard deferred pages removed by type replacement
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md
labels: []
dependencies: []
parent_id: is-01kzwhmcj1b9fngz4nj21p1p7e
created_at: 2026-08-13T07:16:16.510Z
updated_at: 2026-08-13T07:23:49.931Z
closed_at: 2026-08-13T07:23:49.929Z
close_reason: Fixed orphaned deferred-page cleanup for missing and removed pagination sentinels, with regression coverage.
---
Bugbot review thread PRRT_kwDOTX174c6Y2CWn found that immediate folder type replacement can remove descendant pagination sentinels without deleting their pendingTreePages entries. Delete owned pending pages before removing a subtree and make orphan synchronization self-cleaning.
