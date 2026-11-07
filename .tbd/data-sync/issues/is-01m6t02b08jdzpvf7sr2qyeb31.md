---
type: is
id: is-01m6t02b08jdzpvf7sr2qyeb31
title: Align rendered documents with source tabs and dock the TOC on the right
kind: feature
status: in_progress
priority: 2
version: 4
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T03:15:38.119Z
updated_at: 2026-11-07T04:15:04.560Z
---
Align rendered Markdown, its source view, and PR reading content below their leftmost render tab. Keep the existing shared configurable prose measure for README, PR descriptions, comments, and other rendered content. Reuse KPress TOC and rendering, move the wide docked TOC to the right with the standard gap, and preserve the compact toggle and overlay in narrow panes. Verify long and short docs, source and rendered switching, responsive reflow, and the same measure on a checkout and managed repository.

## Notes

PR #320 review corrections at 8bbf33e7, integrated at ab905365, cap embedded README wide tables to their own card so the final columns remain reachable by horizontal scrolling. Manual before/after reproduced the 1238px wrapper clipped by a 709px panel; the fix uses a 662px scroll wrapper and reaches the last column. Standalone documents retain wide-table bleed. CSS assertions now use existing parsed selector/declaration maps. Focused checks pass and the exact-head full gate is running.
