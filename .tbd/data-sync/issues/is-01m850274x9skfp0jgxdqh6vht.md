---
type: is
id: is-01m850274x9skfp0jgxdqh6vht
title: Tooltips wrap long file names instead of running over
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:54.747Z
updated_at: 2026-11-23T20:02:59.631Z
started_at: 2026-11-23T20:02:59.628Z
---
Requested in manual testing: .custom-tooltip (static/styles.css) caps its width at 360 px but sets no wrapping, so a long unbroken name in a treemap tooltip runs past the tooltip's edge. Make every tooltip wrap long names.
