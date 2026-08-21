---
type: is
id: is-01m0k52aw4w2bn7f7zfbfswdk5
title: "File-type colors collide and move between folders: the palette is a slot, not an identity"
kind: bug
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k52aba17zgc5njavnj58xq
parent_id: is-01m0k63zme8wetezbbq59ys3k8
created_at: 2026-08-21T21:54:08.899Z
updated_at: 2026-08-21T22:12:53.932Z
---
Two file types can render in near-identical colors, and a family's color changes between folders. Both follow from the same cause: the palette is positional, not an identity.

`category_palette.js` hashes the family key to a slot in a fixed pool (`assignSlot` -> FNV-1a modulo the slot count), then probes linearly for the next free slot. `DISTRIBUTION_PALETTE_SLOTS` is 12. The registry has 56 families.

That guarantees three defects:

1. Collisions. With more families than slots, the probe exhausts the pool and falls back to `start + 1` without reserving, so two live families get the same color. Measured on this repository's root: `family:json` and `family:audio` both painted oklch(0.604 0.145 151.1); `family:python` and `family:log-files` both painted oklch(0.575 0.1601 276.22).

2. Near-collisions. Adjacent slots sit close in hue, so two families in one folder can be hard to tell apart. Measured: css at hue 137 against json at hue 151, and markdown at hue 38.6 against yaml at hue 54.1.

3. Instability. Because the slot depends on which other families are present and on probe order, the same family is a different color in a different folder. A reader cannot learn "yellow is JavaScript" because it is not.

The fix is to key color to the family itself rather than to a slot, which is also what makes matching GitHub's colors meaningful. The sibling bead covers where those colors come from; this one is the mechanism: a declared color per family, a house color for the 18 non-language families, and a check that no two families in the registry are within a stated perceptual distance of each other.

That check is the part worth keeping: a distance floor stated once fails the build when a new family lands too close to an existing one, instead of leaving it to be noticed in a screenshot.
