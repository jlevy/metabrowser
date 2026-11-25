---
type: is
id: is-01m84fn94wz47am8cwywj3angp
title: "Treemap: file cells lose their top border along the top edge of a packed region"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/752
    at: 2026-11-23T15:51:18.810Z
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-23T15:16:13.594Z
updated_at: 2026-11-25T02:16:20.156Z
closed_at: 2026-11-23T15:51:23.646Z
close_reason: "First-row and first-column cells draw their edge, checked in the paint session and on this repository's live canvas. In #752."
resolution: null
duplicate_of: null
---
In manual testing of the canvas Treemap (layers 4 and 5), file cells along the top edge of a packed region (the first row under a folder's header) often show no top border. Find whether the header fill, the frame, or a half-pixel stroke at the boundary covers it, and fix it so every cell draws all four edges.
