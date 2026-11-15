---
type: is
id: is-01m7ezt35h67ybk1dmmsztsp52
title: "U6: can highlight.js continue a lexer state? If so, highlight the visible lines first and the rest at idle"
kind: task
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m774rbz6q8kxewh1pxe06xv4
  - type: blocks
    target: is-01m774rb30k3bd8ehwy6exbwq4
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:55:11.024Z
updated_at: 2026-11-15T06:55:42.061Z
---
Architecture review uncertainty U6: a twenty-line check. If it holds, H101 (worker highlighting) and H99 (b) (chunked long source) become one row that highlights the viewport first, in place of a worker.
