---
type: is
id: is-01m774r4psqf6bqd00a8pae0dw
title: Parallel shell-tools and KPress asset loading
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774r9n7z8bymhs94yjq67sw
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T05:47:34.487Z
updated_at: 2026-11-12T07:52:59.586Z
started_at: 2026-11-12T05:53:03.657Z
---
Fetch shell-tools scripts in parallel while keeping execution order (asset-loader.js), and KPress CSS and scripts in parallel (plugin-sdk.js loadKpressAssets). Measured as round-trip levels and time to tools ready.

## Notes

Implemented on claude/perf-delivery, PR #372 (191dd8a1 / c0c293bd / 2a682e82; 640e008d moves KPress loading to sdk-views, restoring 3,062 bytes of startup headroom and regenerating the two goldens the stamps changed). Awaiting harness v2 for rounds exp-060 and exp-062.
