---
type: is
id: is-01m774rdb8j84szr2bamkxphvm
title: Bulk Pulls metadata warming when steps are cache reads
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:43.335Z
updated_at: 2026-11-15T06:12:36.794Z
---
Replace the one-step-per-second walk with bulk preparation when steps only read the cache. Measured as background requests per minute.
