---
type: is
id: is-01m268n67pgzr03gg2taf6fb3f
title: Recency filter hides collapsed folders with matching files
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-09-10-functional-ui-cli-parity.md
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-09-10T18:18:08.500Z
updated_at: 2026-09-10T18:36:10.834Z
---
On metabrowser 0.9.2.dev131+632f74bc, selecting Past hour can report the correct filtered total while displaying only one or no file rows. Reproduced with six recent files across three two-file folders: the UI reported Filtered to 6 files, but every folder row received tree-item-filter-hidden. renderTreeNodes keeps collapsed descendants only in subtreeCache, so applyTreeFilters passes only mounted DOM rows to clusterHiddenIds. Each collapsed folder therefore appears to have zero children and is pruned despite its total_files aggregate and cached children. Add a headless integration regression covering the bounded renderer plus recency pruning; the decision must use the complete recent tree or explicit unknown/cached-child state rather than DOM child presence.
