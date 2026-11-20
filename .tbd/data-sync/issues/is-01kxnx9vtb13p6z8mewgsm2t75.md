---
type: is
id: is-01kxnx9vtb13p6z8mewgsm2t75
title: Modularize the browser shell and reader assets
kind: epic
status: open
priority: 2
version: 7
spec_path: TODO.md
labels:
  - browser
  - architecture
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
child_order_hints:
  - is-01kxshfx0fhzyccg1wwtdv7c6b
  - is-01kxsvxrrzqt4c60d15em6jrqe
created_at: 2026-07-16T16:49:04.842Z
updated_at: 2026-11-20T19:15:56.877Z
extensions: {}
---
Split the remaining large classic shell and reader scripts into cohesive core, tree, preview, live-update, and view modules; split corresponding CSS by responsibility; preserve behavior and asset budgets; centralize shared copy/icon helpers; remove redundant legacy host styles; and use the work to retire measured TypeScript/Biome compatibility exceptions.

## Notes

2026-11-20 audit: Browser shell modularization; every child is open.
