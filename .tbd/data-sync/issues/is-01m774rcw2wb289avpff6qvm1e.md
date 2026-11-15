---
type: is
id: is-01m774rcw2wb289avpff6qvm1e
title: Opt-in uncompressed mode for the app's loopback client
kind: task
status: closed
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:42.849Z
updated_at: 2026-11-15T06:55:40.495Z
closed_at: 2026-11-15T06:55:40.494Z
close_reason: "H103 widened into H115 (mb-9uyq), encode once or not at all, per the architecture review (R4): no gzip toward a loopback client is H115 (b)."
resolution: duplicate
duplicate_of: is-01m7ezskcw6392tt1skyt02k5e
---
A server flag the native app sets to skip gzip on loopback. Measured as event-loop time per cold landing.

## Notes

2026-11-14, from #387 (research-2026-11-12-eager-startup-script-cost.md): on loopback the server's gzip costs 0.108 ms per compressed KB on the event loop, and the same startup scripts sent uncompressed reached the first row 32 ms sooner. Input for H103's round.
