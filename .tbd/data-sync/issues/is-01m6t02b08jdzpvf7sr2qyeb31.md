---
type: is
id: is-01m6t02b08jdzpvf7sr2qyeb31
title: Align rendered documents with source tabs and dock the TOC on the right
kind: feature
status: in_progress
priority: 2
version: 3
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-07T03:15:38.119Z
updated_at: 2026-11-07T03:38:22.159Z
---
Align rendered Markdown, its source view, and PR reading content below their leftmost render tab. Keep the existing shared configurable prose measure for README, PR descriptions, comments, and other rendered content. Reuse KPress TOC and rendering, move the wide docked TOC to the right with the standard gap, and preserve the compact toggle and overlay in narrow panes. Verify long and short docs, source and rendered switching, responsive reflow, and the same measure on a checkout and managed repository.

## Notes

Implemented in 8e70af49 and integrated with sidebar work at 389df845. Direct Markdown, Overview README and PR prose share the configured measure and tab-aligned left gutter. Reuses pinned KPress renderer, right-side sticky TOC and compact drawer with trailing icon. Browser verified wide/narrow layouts, section navigation, 80-character reflow, thumbnails and wide tables. 92 focused tests and 18 goldens passed. Final exact-head gate and publication are running.
