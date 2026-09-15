---
type: is
id: is-01m2hrdm4kc5t3kvw1374e9tkj
title: "Walker emit batch: 1,024 measured 1.2 s faster than 256 on a 300k attached walk"
kind: task
status: open
priority: 2
version: 2
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
created_at: 2026-09-15T05:25:16.562Z
updated_at: 2026-09-15T05:38:47.207Z
---
`INVENTORY_WALKER_EMIT_BATCH` is 256 (`settings.py`). Raising it to 1,024 measured an
attached 300k walk at 17.49/17.47/17.67 s against 18.77/18.70/18.47 s at 256 --
non-overlapping, about 1.2 s of the delivery overhead. 1,024 is the contract ceiling:
`MAX_CHANGE_PATHS` is 1,024 and above it a change becomes `all_dirty` and forces a
resync.

Deliberately NOT taken for v0.10.0. A larger batch delays the first emit, and
`first_row_ms` on the flat corpus is the metric the release gate is closest to (392 ms
worst against a 450 ms flat-shape ratchet). Trading a metric at its margin for 4% of
bulk throughput, on a release branch, is the wrong order to do things in.

Only `tests/test_inventory_walk_work.py:276` depends on the constant.

Done when: the change is measured for its effect on `first_row_ms` and on client
transient heap in a real browser, not only for walk completion, and is taken or rejected
on that evidence with the measurement recorded beside the constant.
