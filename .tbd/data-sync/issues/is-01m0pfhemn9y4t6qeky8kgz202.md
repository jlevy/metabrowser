---
type: is
id: is-01m0pfhemn9y4t6qeky8kgz202
title: "H54: the tally row's reservation cannot cover a row that wraps"
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-23T04:54:53.332Z
updated_at: 2026-08-23T07:05:05.425Z
---
The remainder of exp-009. The navigation tally row reserves one line box (min-height: calc(1.5 * var(--nav-font-size) + 13px) on .tree-summary), which is exactly the height of a .tree-summary-split row that fits on one line. On a real tree in a 300px navigation pane the settled row reads like '20,640 files (248.7 MB) +90,030 ignored (1430.1 MB)' and wraps to two lines, standing 56px, so 23px of downward shift remains out of the original 67px.

Raising the floor to two lines is the wrong fix: the row does fit on one line in a wider pane, and every reader with one would trade a jump they never saw for permanent dead space above their tree.

The fix is to make the pending row the same shape as the settled one -- same classes, same cell count, placeholder content sized like the digits that will replace it -- so it wraps the same way the settled row will. treeSummaryHtml() in src/metabrowser/static/app.js emits both rows and is the place to do it.

Metric: summary_shift_px zero at 300px and at a pane wide enough not to wrap, with no idle gap in either. The probe measures it and 'run.py compare' prints it.

See explorations/performance-loop/experiments/exp-009-the-skeleton-stops-growing-under-the-reader.md

## Notes

The exp-009 audit found a better fix than any CSS floor. The live sample caught the tally row already wrapped at 14,826 files mid-scan, so a usable partial count exists long before the walk finishes. If the server inlined that partial tally alongside the rows it already inlines (_INLINE_INITIAL_TREE_ROWS), the row would paint at its settled height and the pending state would not exist. Prefer that to shaping a placeholder that guesses its own wrap. Wrap threshold, measured: the row is 33px at '12 files (4.1 kB)', 33px at '246,282 files (1.7 GB)', 33px at '12 files (4.1 kB) +8 ignored (2.0 kB)', and 56px only at two long counts at once.
