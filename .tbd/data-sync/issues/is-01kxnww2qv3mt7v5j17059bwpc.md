---
type: is
id: is-01kxnww2qv3mt7v5j17059bwpc
title: Remove scoped Biome legacy rule exceptions
kind: chore
status: open
priority: 3
version: 2
spec_path: docs/development.md
labels:
  - tooling
  - biome
  - ratchet
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:41:33.178Z
updated_at: 2026-07-16T16:44:32.973Z
---
Eliminate the file-scoped Biome compatibility exceptions while preserving the recommended global rule floor. The 2026-07-16 baseline is 244 noInnerDeclarations findings across app.js (165), charts.js (27), structured/preview.js (20), structured/tree.js (17), and perf.js (15), plus 24 noDescendingSpecificity findings confined to styles.css. Acceptance: refactor findings, shrink the exact override file lists as files become clean, and delete each override when its count reaches zero.

## Notes

Replaced both global Biome rule disables with exact file overrides after measuring 244 inner-declaration and 24 CSS-specificity findings. devtools/npm_policy.py rejects global regressions and pins the reviewed file sets. Full release gate passes.
