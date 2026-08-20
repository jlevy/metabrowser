---
type: is
id: is-01m0ea4d7260d44gkfv5pw9x4d
title: "Design vocabulary: extend row and chevron enforcement to every surface"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T00:46:27.553Z
updated_at: 2026-08-20T00:46:27.553Z
---
tests/test_design_vocabulary.py now pins the diff bar to the nav tree: one chevron glyph (registry + section-disclosure mask), shared --ui-row-height, shared --hover-bg. Extend the same agreements to the remaining row-like surfaces — git graph commit rows (PR #24 branch), tally tree rows, recents rows, quick-file results — and audit every clickable surface for a design-system hover state. Where a surface deliberately diverges, the design-system doc must say why, or the test must cover it. Rule of the house: prefer a check to a sentence.
