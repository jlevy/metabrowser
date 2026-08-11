---
type: is
id: is-01kxnww2qv3mt7v5j17059bwpc
title: Remove scoped Biome legacy rule exceptions
kind: chore
status: open
priority: 3
version: 4
spec_path: TODO.md
labels:
  - tooling
  - biome
  - ratchet
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:41:33.178Z
updated_at: 2026-07-17T20:20:52.580Z
---
Eliminate the file-scoped Biome compatibility exceptions while preserving the recommended global rule floor. The 2026-07-16 baseline is 244 noInnerDeclarations findings across app.js (165), charts.js (27), structured/preview.js (20), structured/tree.js (17), and perf.js (15), plus 24 noDescendingSpecificity findings confined to styles.css. Acceptance: refactor findings, shrink the exact override file lists as files become clean, and delete each override when its count reaches zero.

## Notes

Replaced both global Biome rule disables with exact file overrides after measuring 244 inner-declaration and 24 CSS-specificity findings. devtools/npm_policy.py rejects global regressions and pins the reviewed file sets. Full release gate passes.
