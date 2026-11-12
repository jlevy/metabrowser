---
type: is
id: is-01m774rcw2wb289avpff6qvm1e
title: Opt-in uncompressed mode for the app's loopback client
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
created_at: 2026-11-12T05:47:42.849Z
updated_at: 2026-11-12T05:48:12.819Z
---
A server flag the native app sets to skip gzip on loopback. Measured as event-loop time per cold landing.
