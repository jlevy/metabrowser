---
type: is
id: is-01m75a2bg9ds5y1n3ga5qf7qkw
title: "PR #351 A16: chooser refinement belongs in #349"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:42:03.144Z
updated_at: 2026-11-11T13:01:12.510Z
started_at: 2026-11-11T13:01:10.040Z
closed_at: 2026-11-11T13:01:12.509Z
close_reason: "declined by the coordinator: the chooser refinement stays its own layer; moving it into #349 needs history rewriting or a revert-and-reapply across two layers, the stack merges atomically, and the layer is independently reviewable"
resolution: null
duplicate_of: null
---
Low, whole-stack layer placement. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
