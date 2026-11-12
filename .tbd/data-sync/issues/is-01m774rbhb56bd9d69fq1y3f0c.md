---
type: is
id: is-01m774rbhb56bd9d69fq1y3f0c
title: One layout per Markdown mount
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
created_at: 2026-11-12T05:47:41.482Z
updated_at: 2026-11-12T05:48:12.803Z
---
Defer the table of contents scroll read until after the swap, or commit without re-parenting. Measured as layout passes over 10 ms and painted-ready.
