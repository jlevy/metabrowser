---
type: is
id: is-01m2h84mc3ddxry9h2g2wx7ffm
title: Transient JS heap is 2.5-3.2x v0.9.1 on a repository-shaped tree
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-09-15T00:40:44.675Z
updated_at: 2026-09-15T00:40:44.675Z
---
exp-034, quiet 4-CPU host, project-10, five back-to-back headed browser pairs. Transient js_heap_mb is 8.0-9.6 MB on the control and 21.4-26.6 MB on the candidate, every pair over the release's 1.3x rule. The retained heap after a forced collection is unchanged: 6.1-6.2 MB against 6.4 MB, so nothing is leaking.

The cause is in the same captures: inventory_delivery_batch_items_max is 256 on the control and 4,096 on the candidate. v0.9.1 had no bound on a delivery batch, so its batch size followed the tree -- 256 items on project-10, and 56,238 items on the 300,000-file corpus, which is what exp-032 set out to bound. The candidate always delivers at most 4,096, which is larger than v0.9.1's batch on this tree and 14 times smaller on a large one. The transient heap follows the batch.

So this is the cost of a bound that pays for itself on a large tree, not a regression to fix by removing the bound. Worth revisiting only if a smaller bound keeps the 300k win: measure the batch size against first_row_ms and interaction latency on both corpora before changing the constant.
