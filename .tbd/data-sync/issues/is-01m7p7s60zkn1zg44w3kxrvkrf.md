---
type: is
id: is-01m7p7s60zkn1zg44w3kxrvkrf
title: Bound KPress's cache in the inert-render child by measured size (#527 C4, C2 idle)
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wyspfffhwcfcze4mke8jjp
created_at: 2026-11-18T02:29:10.814Z
updated_at: 2026-11-20T17:16:21.106Z
---
Deferred from PR #527 C4 and C2's idle part: measure KPress's in-child cache, bound it, and then decide whether the child may outlive _IDLE_S.
