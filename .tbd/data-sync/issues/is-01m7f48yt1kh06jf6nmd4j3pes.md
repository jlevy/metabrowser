---
type: is
id: is-01m7f48yt1kh06jf6nmd4j3pes
title: "Group by: compute every group in one pass over the index; a large folder takes about a second"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-15T08:13:12.384Z
updated_at: 2026-11-15T08:13:12.384Z
---
Found while building mb-sogv (Files Group by, #445, pull request 2 of the 2026-11-15 plan stack).

Group by asks the server for each group's tree with one full pass over the inventory index per group. The author measured it in headless Chrome (server times are the median of 3 requests):

| Folder | Server: ungrouped / by type / by age | Choosing File type until painted |
| --- | --- | --- |
| 22,104 files | 34 / 106 / 58 ms | 114–163 ms |
| 100,000 files (synthetic) | 121–194 / 724–909 / 490–515 ms | 1,062–1,137 ms (662–828 ms with the menu-open prefetch) |

While a grouping loads, the old tree stays on screen and the trigger breathes. Even so, a second at 100,000 files is well past the "effortlessly fast" budget. Opening the Group by menu also prefetches both groupings, which is wasted work if the reader then picks nothing.

Done when:
- the provider computes every group's membership and counts in one pass over the index;
- choosing a grouping on the 100,000-file fixture paints within the same budget as choosing No grouping, with the measurement recorded beside the code per AGENTS.md's "Measure before bounding";
- the prefetch on menu open asks only for what is likely to be chosen, or costs what one pass costs;
- the route golden (`cli-api-tree-groups.tryscript.md`) is unchanged.
