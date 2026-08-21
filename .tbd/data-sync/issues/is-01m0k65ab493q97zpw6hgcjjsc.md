---
type: is
id: is-01m0k65ab493q97zpw6hgcjjsc
title: "Phase 2: every surface reads the declared color"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
labels: []
dependencies: []
parent_id: is-01m0k63zme8wetezbbq59ys3k8
created_at: 2026-08-21T22:13:15.234Z
updated_at: 2026-08-21T22:13:15.234Z
---
Phase 2 of the spec: everything that draws a file reads its color from the registry.

category_palette.js stops hashing. A family's color arrives in the projection the browser already receives, so the FNV-1a hash, the linear probe, the slot pool, and DISTRIBUTION_PALETTE_SLOTS all go, and with them the collisions and the instability they caused.

The same field feeds the Folder Overview distribution, the Treemap, and the navigation file icons, so one family is one color everywhere rather than one color per surface per directory.

Tests: two families never resolve to the same color, and a family's color does not depend on which other families are present — the second is the one that fails today, and the one a reader actually notices when the same folder looks different after adding a file.
