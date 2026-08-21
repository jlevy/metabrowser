---
type: is
id: is-01m0hj1n6r1sqrabjrxat3a6xp
title: Nav selection box narrows and shifts right with depth
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0hhjf2e1w8tp30ay4tj8183
created_at: 2026-08-21T07:02:29.335Z
updated_at: 2026-08-21T07:02:29.335Z
---
Nav rows narrow and shift right with nesting depth, so the hover background, the selected background, and the 2px accent bar all start further in at each level.

Measured in the running app at a 299px panel width: a level-1 row spans left 0 to right 299; a level-2 row spans left 16 to right 299. Every level costs another 16px of row box.

Cause: `.tree-children { margin-left: 16px; }` in static/styles.css indents the container, so the rows inside it are physically narrower. Indentation and row geometry are the same thing today.

Wanted: every row box spans the full panel width at every depth, with indentation applied inside the row instead. Rows already carry `data-tree-level` / `aria-level` from `treeItemAttributes`, so the depth is available to CSS without new markup; the row can take a depth-derived `padding-left` while `.tree-children` keeps no margin of its own. The full-width box is also the larger click target for expanding.
