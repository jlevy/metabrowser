---
type: is
id: is-01m774rb30k3bd8ehwy6exbwq4
title: "H99 (b): chunk long source views (H99 (a) merged into H112); one row with H101 after U6"
kind: task
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rdstn0r4rtfnn10sdbp9
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T05:47:41.023Z
updated_at: 2026-11-15T06:55:43.463Z
---
content-visibility hidden for shown-once views (bounded), content-visibility auto chunks for long source and raw views. Measured as heavy view-tab revisit and long tasks.

## Notes

2026-11-14: H99 (a), keeping hidden view tabs laid out, merged into H112 (mb-wki1). This bead keeps H99 (b), chunking long source with content-visibility, which competes with H101 for the same longest task; the architecture review makes them one row after U6 (mb-xws3), whether highlight.js can continue a lexer state.
