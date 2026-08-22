---
type: is
id: is-01m0nefvhy0sc1p6k3mfxyszp2
title: Nav header tally is 12px against the 13px file rows beside it
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:17:18.014Z
updated_at: 2026-08-22T19:28:05.920Z
closed_at: 2026-08-22T19:28:05.920Z
close_reason: Tally now paints at --nav-font-size like the rows it summarises.
---
Reported in QA: the '305 files (11.7 MB) + 621 ignored (40.9 MB)' row at the top of the nav panel looks smaller than the file names. It is not optical.

styles.css .tree-item sets font-size: var(--nav-font-size), which is 13px. The tally spans -- .tree-summary-count, -size, -tracked, -bytes, -ignored -- all set var(--ui-small-font-size), which is 12px. So the header row runs one step down the ramp from the rows it summarises.

Weight already matches: neither sets font-weight, so both inherit normal (400).

Fix: paint the tally at --nav-font-size like the rows. Check the wrap behaviour afterwards -- .tree-summary-split wraps at gap 4px 5px inside a 300px --tree-pane-width, and a size bump can push '+ 621 ignored (40.9 MB)' onto a second line at narrower pane widths. Keep the muted colour on the ignored half; only the size is wrong.
