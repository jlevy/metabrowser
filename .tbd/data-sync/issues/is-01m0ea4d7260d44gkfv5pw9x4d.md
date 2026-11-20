---
type: is
id: is-01m0ea4d7260d44gkfv5pw9x4d
title: "Design vocabulary: extend row and chevron enforcement to every surface"
kind: task
status: open
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-08-20T00:46:27.553Z
updated_at: 2026-11-20T17:17:26.548Z
---
tests/test_design_vocabulary.py pins the diff bar to the nav tree: one chevron glyph (registry plus section-disclosure mask), shared --ui-row-height, shared --hover-bg. The row-text baseline and vertical keyboard checks also cover git graph and Pulls rows. Extend the height and hover agreements to the remaining row-like surfaces — git graph commit rows, Pulls rows, tally tree rows, recents rows, quick-file results — and audit every clickable surface for a design-system hover state. Where a surface deliberately diverges, the design-system doc must say why, or the test must cover it. Prefer a check to a sentence.
