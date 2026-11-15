---
type: is
id: is-01m774ra6cpn1h8jnk2mkzq0nh
title: First-view readiness independent of visibility
kind: task
status: open
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rerk521sprp8ys3ana0t
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:40.107Z
updated_at: 2026-11-15T06:12:33.833Z
---
A hidden page finishes its first view so a hidden web view can be prewarmed and shown ready. Measured in WKWebView as show-to-ready.

## Notes

2026-11-14: unblocked; the WKWebView probe mb-fevz landed in #378 (a1347646).
