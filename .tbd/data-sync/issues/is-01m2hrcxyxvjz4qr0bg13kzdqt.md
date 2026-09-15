---
type: is
id: is-01m2hrcxyxvjz4qr0bg13kzdqt
title: "Flat mega-tree: Long Tasks appear where v0.9.1 had none"
kind: bug
status: open
priority: 2
version: 1
labels:
  - performance
dependencies: []
created_at: 2026-09-15T05:24:53.853Z
updated_at: 2026-09-15T05:24:53.853Z
---
On the 300k flat corpus, two of five candidate runs record Long Tasks of 98 ms and 75 ms;
all five v0.9.1 runs record zero. Total blocking time follows, 0 ms against up to 83 ms.

Both values are inside the 200 ms `long_task_max_ms` budget, so this does not fail a
gate. It is recorded because growth from zero is the signal, and because the loop's own
rule is that `long_task_max_ms` must not grow. On the repository-shaped project-10
corpus every run of both conditions records zero, so this is specific to the flat shape.

Likely the same delivery-path work as the sibling beads, surfacing as a single long
callback rather than as throughput. Confirm that before assuming it.

Done when: the flat shape records no Long Task that v0.9.1 does not, or the cause is
identified and the growth is explained as something other than delivery cost.
