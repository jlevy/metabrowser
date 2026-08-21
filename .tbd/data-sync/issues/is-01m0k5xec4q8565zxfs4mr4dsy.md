---
type: is
id: is-01m0k5xec4q8565zxfs4mr4dsy
title: Render nav rows from partial index state instead of gating on scan completion
kind: task
status: open
priority: 0
version: 8
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k5xeqm8ab1sm4wddc99ahs
  - type: blocks
    target: is-01m0k5xf3ej2n2b7f3zawg9r1p
  - type: blocks
    target: is-01m0k5xfv51f1d214g0fytptqs
  - type: blocks
    target: is-01m0k5xg6xhbr1tp13ypkr40fh
  - type: blocks
    target: is-01m0k5xgjk52878pqq338fzf12
  - type: blocks
    target: is-01m0k5xgycxymyreh03tax0t1q
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:57.220Z
updated_at: 2026-08-21T22:48:50.477Z
---
The largest single win in this plan: 4.2 s at 100k files, 22 s at 1M.

The data is already there. Measured waterfall on a 100k tree:
  t+  319 ms  /api/tree      38 ms   387,778 B   <- usable tree data is in the browser
  t+1,063 ms  /api/events  3,669 ms              <- blocks while the walker converges
  t+4,733 ms  /api/catalog    98 ms 4,580,060 B
  t+4,936 ms  first [role="treeitem"] painted

The server is already built for the opposite behavior: the first /api/tree answers in 3 to 9 ms with partial data at every corpus size, because the walker publishes as it goes. The client does not use that.

Find what gates the first row on scan completion and render from partial index state instead, refining as the walk progresses. Pair with mb-s8yx so an incomplete tree reads as incomplete rather than as an empty one.

This must land before the Phase 3 server work (mb-kp6c, mb-r4bm, mb-migx): a client that waits for the scan makes every server cost look like scan cost.
