---
type: is
id: is-01m7p8a87hrbqjk05z0mbm5hrd
title: Decide whether cache-clear empties a store's manifest bank
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:38:30.128Z
updated_at: 2026-11-18T02:38:30.128Z
---
Review of #533 (C3). The bank keeps one manifest per pull request ever prepared in a store, and cache-clear (clear_pulls) leaves it, as documented. Emptying github-pull-manifests/ under cache-clear is safe against unlocked writers (a missing epoch is re-established at random) and would also sweep v0.12's slot files; it changes cache-clear's documented scope.
