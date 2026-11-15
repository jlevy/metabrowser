---
type: is
id: is-01m7ezskcw6392tt1skyt02k5e
title: "H115: encode once, or not at all — stamped assets compressed once in memory, and no gzip toward a loopback client"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7ezsmvy8gsgc3g9d1x7dnt3
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:54:54.875Z
updated_at: 2026-11-15T06:55:15.605Z
---
Architecture review R4; widens H103 (mb-e500). Decides (a) serial server time for the landing's 41 startup assets 98–106 → ≤ 30 ms, (b) encode 12.3 → 0 ms on a 311 KB render. Needs Server-Timing summed to the end of each body over one landing (H103's blocker), or the review's static probe committed. Reserved exp-095. Registry row H115.
