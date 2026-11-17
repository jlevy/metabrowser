---
type: is
id: is-01m7kp7kkvd7mqey9qswckbk82
title: Record inventory backend decisions D1-D19 in the provider architecture
kind: task
status: closed
priority: 1
version: 9
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kp7kywbn845wb69cy1aca0
  - type: blocks
    target: is-01m7kp7mn0pb2xvh3cwa7akam7
  - type: blocks
    target: is-01m7kp7nba9sw577y4k2cesvbb
  - type: blocks
    target: is-01m7kp7nppf4swardrp6c2gj8y
  - type: blocks
    target: is-01m7kp7q43wpwgn8qatzgvqjwr
  - type: blocks
    target: is-01m7krf558hqc66yc8d6qabedg
parent_id: is-01m0r8xt95921dabcddjjm7csf
hold: null
hold_until: null
created_at: 2026-11-17T02:44:00.251Z
updated_at: 2026-11-17T08:36:25.373Z
started_at: 2026-11-17T07:16:25.842Z
closed_at: 2026-11-17T08:36:25.373Z
close_reason: "Delivered in jlevy/metabrowser#507 (decisions record) and #508 (conformance neutrality); #508, which contains both, is CI green. #507's one red test is the pre-existing storage race mb-532r."
resolution: null
duplicate_of: null
---
Write decisions D1-D19 from docs/project/research/research-2026-11-17-fdu-backend-revisited.md into docs/project/architecture/arch-inventory-provider.md, with D13 (paging under version movement) and D14 (native failure isolation) pinned by new conformance cases.
