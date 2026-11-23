---
type: is
id: is-01m83cd9zc3vte359rgjd3jcpz
title: "PR #722 A3: equal weights expand in near pre-order, not level order"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m836qya23kghgk2m3t9em8nc
created_at: 2026-11-23T05:00:12.103Z
updated_at: 2026-11-23T05:00:19.654Z
closed_at: 2026-11-23T05:00:19.651Z
close_reason: "fixed: in `feabdb162`: the heap key is `(-weight, level, path, sequence)`; confirmed by `test_zero_weight_tree_expands_level_by_level`, which fails on the old key"
resolution: null
duplicate_of: null
---
Review A on https://github.com/jlevy/metabrowser/pull/722, finding A3 (Low): equal weights expand in near pre-order, not level order.
