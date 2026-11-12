---
type: is
id: is-01m776jfvntrcaaj0pa2agmss7
title: "PR #362 D1: a failed log claim falls back to the shared log without a lease"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m776j8hxq7djw7fdr69cdhxd
created_at: 2026-11-12T06:19:26.452Z
updated_at: 2026-11-12T06:25:08.321Z
closed_at: 2026-11-12T06:25:08.320Z
close_reason: "D1 fixed in 8ea75f81: FolderLog claims the folder's log before each launch, and a failed claim fails the launch (Retry claims again); FolderLogTests, red against the earlier fallback"
resolution: null
duplicate_of: null
---
Medium finding D1 on PR #362 (apps/macos/Sources/Metabrowser/FolderSession.swift:44). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5869938647
