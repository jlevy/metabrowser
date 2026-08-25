---
type: is
id: is-01m0vyazy5v54xpz9rrrf5eqhr
title: "PR #74 review MB74-D3: prohibit adapter-side refresh iteration"
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
created_at: 2026-08-25T07:49:42.468Z
updated_at: 2026-08-25T07:59:02.378Z
started_at: 2026-08-25T07:49:47.217Z
closed_at: 2026-08-25T07:59:02.377Z
close_reason: "Fixed: architecture and adoption gates prohibit adapter-side iteration and require one native bounded fdu refresh batch, commit, cursor, and receipt."
resolution: null
duplicate_of: null
---
RefreshRequest is one bounded atomic batch while fdu currently refreshes one path at a time. Make the adoption gate explicit: the adapter must not translate one request into N commits; fdu-nlhl owns the native batch. Origin: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5407035634
