---
type: is
id: is-01m7ezsjf9ak1wnyt1dmr1yfsw
title: "H113: Markdown render by GET — heading anchors from the rendered headings, so a document without wiki syntax skips the worker and the upload"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7ezsmvy8gsgc3g9d1x7dnt3
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:54:53.928Z
updated_at: 2026-11-15T06:55:14.812Z
---
Architecture review R2. Replaces H90's render cache (code at 6b876c54 is the fallback). Decides post_body_bytes → 0, worker module requests 3 → 0, the content's request level 13 → ≤ 9, and files.cold.markdown_mid one frame earlier by exp-087's later-frame test. Needs anchors after render, a tighter wiki trigger, and an entity tag on GET /api/kpress/render. Reserved exp-093. Registry row H113.
