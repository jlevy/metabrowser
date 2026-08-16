---
type: is
id: is-01kxnx9vtb13p6z8mewgsm2t75
title: Modularize the browser shell and reader assets
kind: epic
status: open
priority: 2
version: 2
spec_path: TODO.md
labels:
  - browser
  - architecture
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:49:04.842Z
updated_at: 2026-08-16T08:05:43.117Z
extensions:
  linear:
    id: fb70400d-cf16-4be7-b0c6-8ff45c3730da
    linked_at: 2026-08-16T08:05:43.117Z
---
Split the remaining large classic shell and reader scripts into cohesive core, tree, preview, live-update, and view modules; split corresponding CSS by responsibility; preserve behavior and asset budgets; centralize shared copy/icon helpers; remove redundant legacy host styles; and use the work to retire measured TypeScript/Biome compatibility exceptions.
