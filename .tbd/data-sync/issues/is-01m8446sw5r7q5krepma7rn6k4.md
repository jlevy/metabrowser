---
type: is
id: is-01m8446sw5r7q5krepma7rn6k4
title: "Review layer 4: treemap canvas (PR 752)"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
created_at: 2026-11-23T11:56:04.846Z
updated_at: 2026-11-25T02:16:20.156Z
closed_at: 2026-11-23T11:56:16.703Z
close_reason: Findings fixed in 474b7b0ea on PR 752; the family-hover cost is measured under mb-72rg.
resolution: null
duplicate_of: null
---
Independent review of be7cad5c2. Four bugs: hit grid against unsnapped rects (up to 23% wrong cell), focus reset to the first cell on relayout, '|' in an extension corrupting the style key, a stale pointer re-hit-tested after the viewport moved. Test gaps: no theme repaint test, fill check not against probe colors, mark-op test by construction. Nits: separator pixels in the lift, an unclipped interior, fractional-DPR resampling, an unmeasured family-hover cost (folded into mb-72rg), dead CSS. All fixed in 474b7b0ea except the hover cost.
