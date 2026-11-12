---
type: is
id: is-01m774ramhp4w2e08j3t30aw9g
title: Detached LRU of file surfaces with a suspend and resume view contract
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:40.559Z
updated_at: 2026-11-12T05:48:12.787Z
---
Retain recently viewed file surfaces detached, keyed by path and ETag, budgeted by DOM nodes; SDK suspend()/resume() hooks with a version bump. Measured as revisit painted-ready and requests, plus memory.
