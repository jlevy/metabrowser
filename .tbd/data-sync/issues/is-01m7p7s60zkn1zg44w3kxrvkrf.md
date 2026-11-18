---
type: is
id: is-01m7p7s60zkn1zg44w3kxrvkrf
title: Bound KPress's cache in the inert-render child by measured size (#527 C4, C2 idle)
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m75fzpspek15x7d5dqhnc2yw
created_at: 2026-11-18T02:29:10.814Z
updated_at: 2026-11-18T02:29:10.814Z
---
Deferred from PR #527 C4 and C2's idle part: measure KPress's in-child cache, bound it, and then decide whether the child may outlive _IDLE_S.
