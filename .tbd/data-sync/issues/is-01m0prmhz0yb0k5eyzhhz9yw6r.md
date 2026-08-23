---
type: is
id: is-01m0prmhz0yb0k5eyzhhz9yw6r
title: "PR #72 review R1: probe records cls as 0, never null — the gate is inverted"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:33:52.223Z
updated_at: 2026-08-23T08:07:16.690Z
closed_at: 2026-08-23T08:07:16.690Z
close_reason: Fixed in 02c3105. Gated cls and cls_shifts on visibility and dropped the always-true 'unshifted.length >= 0' clause. Three new recorded runs report null.
---
explorations/performance-loop/probe.js:229. 'laidOut && unshifted.length >= 0' — the second clause is true for every array, so the gate is just laidOut, true in any sized pane. Records 0 where the PR says null. All 10 new runs.jsonl rows carry cls:0 with page_visible:false. Fix: gate on 'visible', drop the always-true clause, and null out or drop the field in the recorded rows.
