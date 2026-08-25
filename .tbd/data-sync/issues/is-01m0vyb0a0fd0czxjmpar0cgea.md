---
type: is
id: is-01m0vyb0a0fd0czxjmpar0cgea
title: "PR #74 review MB74-D4: prohibit dishonest adapter flat paging"
kind: bug
status: closed
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m0vyaj3yjgs2p8mvt4y41b43
hold: null
hold_until: null
created_at: 2026-08-25T07:49:42.847Z
updated_at: 2026-08-25T07:59:02.665Z
started_at: 2026-08-25T07:49:47.224Z
closed_at: 2026-08-25T07:59:02.664Z
close_reason: "Fixed: architecture and adoption gates require native version-pinned flat paging with mandatory bounds and exact remainders; fake terminal pages, unbounded FFI, and mirrors are forbidden."
resolution: null
duplicate_of: null
---
CatalogProjection and FilteredTreeProjection require bounded lossless version-pinned pages while fdu lacks flat continuation. Make the adoption gate explicit: the adapter must not truncate, mirror, or claim a false remainder; fdu-91ru owns native paging. Origin: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5407035634
