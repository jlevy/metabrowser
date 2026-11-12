---
type: is
id: is-01m774rdb8j84szr2bamkxphvm
title: Bulk Pulls metadata warming when steps are cache reads
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:43.335Z
updated_at: 2026-11-12T05:48:12.826Z
---
Replace the one-step-per-second walk with bulk preparation when steps only read the cache. Measured as background requests per minute.
