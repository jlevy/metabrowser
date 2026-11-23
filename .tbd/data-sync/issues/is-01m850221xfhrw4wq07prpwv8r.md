---
type: is
id: is-01m850221xfhrw4wq07prpwv8r
title: Treemap labels go down to a smaller minimum size
kind: task
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:49.530Z
updated_at: 2026-11-23T20:02:57.488Z
started_at: 2026-11-23T20:02:57.487Z
---
Requested in manual testing: the label floor is labelMinPx 11 px, with labelMinW/labelMinH (56/16 full, 44/14 compact) in treemap-map.js SIZE_PRESETS. Lower the floor so smaller cells are labelled, keeping thresholds tied to the type so labels still fit.
