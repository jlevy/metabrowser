---
type: is
id: is-01m7rwjtqep1zqb91jyq9pnxc9
title: Inventory rewalk keeps indexed children it no longer finds until their delete event arrives
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T03:11:11.597Z
updated_at: 2026-11-19T03:11:11.597Z
---
From #598 (mb-3ot0): a rewalk does not remove indexed children it no longer finds, so a missed delete is counted until its delete event arrives. Removing those rows must respect max_depth rewalks. Documented in arch-inventory-engine-python.md.
