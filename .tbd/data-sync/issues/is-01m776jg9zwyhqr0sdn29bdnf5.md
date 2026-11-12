---
type: is
id: is-01m776jg9zwyhqr0sdn29bdnf5
title: "PR #362 D2: readiness attachment bypasses load-ticket invalidation"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m776j8hxq7djw7fdr69cdhxd
created_at: 2026-11-12T06:19:26.910Z
updated_at: 2026-11-12T06:25:08.807Z
closed_at: 2026-11-12T06:25:08.806Z
close_reason: "D2 fixed in a0b9680e: PageLoads tickets every load of the next page, readiness included, checked just before taking it; PageLoadsTests, red with take(for:) ignoring its ticket"
resolution: null
duplicate_of: null
---
Medium finding D2 on PR #362 (apps/macos/Sources/Metabrowser/BrowserWindowController.swift:157). Review: https://github.com/jlevy/metabrowser/pull/362#pullrequestreview-5869938647
