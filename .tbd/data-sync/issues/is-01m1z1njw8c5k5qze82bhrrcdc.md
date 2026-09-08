---
type: is
id: is-01m1z1njw8c5k5qze82bhrrcdc
title: Avoid unused full-tree work in Recent queries
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T23:01:20.390Z
updated_at: 2026-09-08T00:02:46.335Z
closed_at: 2026-09-08T00:02:46.333Z
close_reason: "Recent skips unused children topology and folds extension filters once. Same 60k corpus and result rows: cProfile 613017 calls/223ms before, 127551 calls/49ms after. Serving regressions remain separately tracked in mb-5no9."
resolution: null
duplicate_of: null
---
Measured 60,000-file profile: Recent builds and sorts a children graph it never consumes (99 ms of a profiled 223 ms), and folds its extension filter once per entry (180,000 folds for two extensions). Split graph demand from path lookup and precompute the filter; compare identical queries and preserve conformance.
