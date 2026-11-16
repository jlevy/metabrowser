---
type: is
id: is-01m7k58sxt39xnf5cfd3ct05p8
title: Each Pulls row has a third line, its brief change line ('21 A, 15 M, 7 D · +1,234 −567'), which carries the chevron for its changed files, collapsed by default
kind: feature
status: open
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
child_order_hints:
  - is-01m7k58ts482vv1rh5fe1b96dr
  - is-01m7k58vaskn60ztckx9zeyyfz
  - is-01m7k58wccbmkccmwgm6rm7vk9
created_at: 2026-11-16T21:47:33.689Z
updated_at: 2026-11-16T21:47:36.200Z
---
Owner, 2026-11-16: 'We should have the abbreviated summary for "21 A, 15 M, 7 D +1,234 −567" just as it is on a third line in the nav bar for each PR, and then make that the chevron collapsible part, with the file change summary below it, by default not expanded. In this way, we don't have the pull request expansion be as extensive initially, and we don't auto-open it unless the user clicks on the actual chevron. Then, when they do up and down arrows, it doesn't open the PR review items. It lets them see the size of each change. And by pressing Enter, they could open the expanded view there, but only on the summary line. this is an abbreviated summary line, so it doesn't mention the total number of file changes. It just lists the adds, removes, deletes, and line changes in exactly the same format, with a small bullet in between them. In the same coloring as on our other summaries'
