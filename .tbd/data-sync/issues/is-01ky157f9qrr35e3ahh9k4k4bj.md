---
type: is
id: is-01ky157f9qrr35e3ahh9k4k4bj
title: "PR13/R1: global rollup response budget (node + payload cap)"
kind: bug
status: closed
priority: 0
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-21T01:39:13.836Z
updated_at: 2026-07-21T02:01:47.947Z
closed_at: 2026-07-21T02:01:47.945Z
close_reason: "Fixed in the R1-R8 review-response commit on PR #13; verified by new unit/vm assertions plus a live browser pass (hostile filenames, Back/Forward zoom trail, live header); make verify green"
---
Review finding R1 (high): top is per-directory so a balanced 40x40x40 tree emits ~65k nodes / ~8MB JSON at defaults. Fix: global emitted-node budget in rollup() spent in size order (children past budget become children:null lazy sentinels), ROLLUP_MAX_NODES setting, adversarial branching test asserting node count and serialized bytes, correct the spec's budget claims.
