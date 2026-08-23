---
type: is
id: is-01m0p5ycf1p929xak3kt1fsjdf
title: Fold rollup entries at or below a 1% share, not just past a row cap
kind: feature
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-23T02:07:11.328Z
updated_at: 2026-08-23T02:29:07.374Z
closed_at: 2026-08-23T02:29:07.373Z
close_reason: Fixed on claude/rollup-icon-fixes; verified in a browser.
---
The "N more" expander in the file-type rollups shows a fixed number of entries and folds the rest. When the tail is long and thin -- dozens of extensions with a handful of files each -- the visible rows are mostly noise, and the reader pays attention to entries that cannot matter.

REQUESTED RULE: an entry is only shown if it is worth showing AND there is room for it. Concretely, the visible count is the LOWER of:

- the entries above a 1% share, and
- the current maximum number of rows per subsection.

An entry at or below 1% is always folded, however few rows are on screen. Whichever bound is tighter wins, so a long thin tail collapses on the share rule and a short fat list still respects the row cap.

THE SHARE IS OF WHATEVER IS BEING MEASURED. The rollup has a files/bytes toggle, so 1% means 1% of files in files mode and 1% of size in bytes mode. An entry can therefore be visible in one mode and folded in the other, which is correct: it is a statement about the metric on screen, not about the entry.

Points to settle while doing it:
- Where the 1% is written down. It is a claim about what is worth a row, so it wants to sit with the existing row cap and be reachable from the same place.
- The folded count in the expander label has to stay accurate under both bounds, and under the mode switch.
- The existing cap is per subsection; confirm the share is computed against the same population the percentages in those rows are computed against, not against the folder total, or the two numbers on one row will disagree.
