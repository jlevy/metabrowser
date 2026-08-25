---
type: is
id: is-01m0vyazg3dmd8cjbh473z761m
title: "PR #74 review MB74-D2: decide ownership of the semantic file budget"
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m0vyaj3yjgs2p8mvt4y41b43
hold: null
hold_until: null
created_at: 2026-08-25T07:49:42.018Z
updated_at: 2026-08-25T07:49:47.210Z
started_at: 2026-08-25T07:49:47.210Z
---
InventoryConfig.max_files is fingerprinted scope and the Python provider preserves a partial discovery prefix, while fdu cannot yet honor it. Decide and document the joint contract without weakening Phase 1 functionality; cross-link fdu-97dd. Origin: https://github.com/jlevy/metabrowser/pull/74#issuecomment-5407035634
