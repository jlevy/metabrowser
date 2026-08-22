---
type: is
id: is-01m0nsv99stqcjdvf7f13k8kyt
title: "Nav panel and view share one top structure: path row, hairline, tabs row, hairline"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:35:46.872Z
updated_at: 2026-08-22T23:42:30.412Z
closed_at: 2026-08-22T23:42:30.412Z
close_reason: "Both path rows take height and hairline from --pane-header-row-height; measured in a browser: path rows 41px both ending at 41, tabs rows 30.5px both ending at 71.5. Test asserts both read the shared token rather than measuring."
---
The nav panel and the main view should have exactly the same structure at the top, so the two sides of the divider read as one band rather than as two panels that happen to be adjacent.

REQUIRED STRUCTURE, both sides, in this order:

1. A path row -- the folder name and gear on the nav side, the full address and summary on the view side.
2. A hairline.
3. A tabs row -- FILES / GIT on the nav side, OVERVIEW / TREEMAP on the view side.
4. A hairline.

Each row is the SAME HEIGHT on both sides, so every hairline meets its opposite number exactly across the divider and nothing steps up or down as the eye crosses it.

Today the nav header has no bottom rule at all while the main view's `.file-header` has one, so the line stops at the divider and picks up again on the other side. The rows are also not built to a shared height -- the nav header's padding changed when the wordmark moved out of it (mb-hqth), so the two are aligned by coincidence rather than by construction.

Use the same token and weight for every rule (`border-bottom: 1px solid var(--border)`), and drive both rows' height from one place, so a change to either side cannot silently break the alignment. A look-alike value on each side is what produced the current state.

Worth a check that lands with it: the heights are asserted, not eyeballed, since a one-pixel drift is exactly what this is meant to prevent and is invisible in review.
