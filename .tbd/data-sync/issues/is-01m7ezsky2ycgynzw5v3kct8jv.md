---
type: is
id: is-01m7ezsky2ycgynzw5v3kct8jv
title: "H116: one git process per comparison — one diff --patch-with-raw --numstat in place of four sequential git processes"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:54:55.425Z
updated_at: 2026-11-15T06:55:15.997Z
---
Architecture review R5. Decides git;dur on /api/plugin/diff/comparison 82–118 → ≤ 45 ms, processes per comparison 4 → ≤ 2, commits.cold.2 and .3 painted ready 146–160 → ≤ 112 ms; answers byte-identical. Needs git-route-pairs.mjs extended to the comparison route with a process count. Reserved exp-096. Registry row H116.
