---
type: is
id: is-01m850274x9skfp0jgxdqh6vht
title: Tooltips wrap long file names instead of running over
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-22-treemap-canvas-granularity.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/764
    at: 2026-11-23T20:35:18.031Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:54.747Z
updated_at: 2026-11-25T02:16:20.156Z
started_at: 2026-11-23T20:02:59.628Z
closed_at: 2026-11-23T20:35:18.698Z
close_reason: "Done in PR #764 (layer 8 of stack #725)"
resolution: null
duplicate_of: null
---
Requested in manual testing: .custom-tooltip (static/styles.css) caps its width at 360 px but sets no wrapping, so a long unbroken name in a treemap tooltip runs past the tooltip's edge. Make every tooltip wrap long names.
