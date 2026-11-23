---
type: is
id: is-01m836hpsa4m1zk5z2ddmrkd0e
title: "Treemap: tiny cells render past their parents (CSS padding and border floor)"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T03:17:44.820Z
updated_at: 2026-11-23T05:31:37.629Z
started_at: 2026-11-23T03:18:19.655Z
closed_at: 2026-11-23T05:31:37.615Z
close_reason: "fixed in 01cfb5aab and 538eead8a: inset edge and no padding on bare cells, compact padding on labelled cells only; test_treemap_containment_chrome reads both maps (0 escapes)"
resolution: null
duplicate_of: null
---
Owner saw boxes extending outside their parents after the layout containment fix. Measured on the metabrowser repo's compact map: 11 of 124 cells overflow by 0.6-4.3 px. The layout's rectangles are contained, but .tm-cell is border-box with padding 1px 4px (compact 0 3px) and a 1px border, so a cell narrower than padding+border renders at that floor (a 1.7 px cell renders 8 px wide). Fix in the map: cells with no label drop padding, borders must not widen a cell, and the layout must not emit cells below the size the CSS can draw. Pin with a rendered-DOM containment check.
