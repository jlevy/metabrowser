---
type: is
id: is-01kxnww2qv3mt7v5j17059bwpc
title: Remove scoped Biome legacy rule exceptions
kind: chore
status: open
priority: 3
version: 7
spec_path: TODO.md
labels:
  - tooling
  - biome
  - ratchet
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:41:33.178Z
updated_at: 2026-11-14T18:46:25.143Z
extensions:
  linear:
    id: 548aa569-c8d3-4796-9230-906592cb0796
    linked_at: 2026-08-16T08:05:55.601Z
---
Eliminate the file-scoped Biome exceptions in biome.json's overrides while keeping the recommended global rule floor. Two remain: noDescendingSpecificity off for src/metabrowser/static/styles.css, and noInnerDeclarations off for static/app.js, charts.js and perf.js and builtin_plugins/structured/preview.js and tree.js. Refactor the findings, shrink each override's file list as files become clean, and delete an override when its list is empty. The Biome upgrade in mb-1jq3 raises noDescendingSpecificity outside styles.css as well (builtin_plugins/folder/file_type_summary.css), so take the two together or in order.

## Notes

Replaced both global Biome rule disables with exact file overrides after measuring 244 inner-declaration and 24 CSS-specificity findings. devtools/npm_policy.py rejects global regressions and pins the reviewed file sets. Full release gate passes.
