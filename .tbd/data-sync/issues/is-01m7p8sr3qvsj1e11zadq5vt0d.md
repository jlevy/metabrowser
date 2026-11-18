---
type: is
id: is-01m7p8sr3qvsj1e11zadq5vt0d
title: "Treemap tab: the same file-type legend as the File Overview, with the same hover behavior (every matching region highlighted, darker, eased, gentle shimmer on regions and the entry)"
kind: feature
status: in_progress
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:46:57.910Z
updated_at: 2026-11-18T03:38:33.007Z
started_at: 2026-11-18T03:21:45.861Z
---
Owner, 2026-11-18 in chat: 'we should add the same legend to the treemap tab. And the same behavior'. Reuse the File Overview's legend builder and the shared hover store (distribution-hover.js) rather than a second implementation; the treemap's bars currently keep a hover of their own (noted in #516's review A). Stack on the legend-hover PR (mb-z6hb).

## Notes

PR #547 (claude/treemap-legend, base claude/legend-hover-all-bars = #545), stack #548, opened 2026-11-18 at f865ebc: Treemap shows File Overview's legend via distribution-legend.js and buildFileTypeLegendModel; cells, bars, and legend share distribution-hover.js (bars no longer keep their own); entry marks every cell of its family's color, its segments, and itself; cell or segment marks itself and its entry; cells lift and shimmer, no growth. Golden cli-ui-treemap-legend, Chrome test_treemap_legend_hover_chrome.
