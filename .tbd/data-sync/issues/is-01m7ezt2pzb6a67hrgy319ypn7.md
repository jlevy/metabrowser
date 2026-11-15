---
type: is
id: is-01m7ezt2pzb6a67hrgy319ypn7
title: "U5: the native app's frame rate — WebKit drew 30 frames a second in Low Power Mode"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:55:10.558Z
updated_at: 2026-11-15T07:26:42.581Z
---
Architecture review uncertainty U5 (docs/large-content-rendering.md). Read frame gaps with wkprobe.mjs, so the 50 ms goal is stated in frames for the app. Lane W.

## Notes

2026-11-15 (#441 re-review): the instrument does not exist yet. wkprobe records show_to_first_frame but no frame gaps; build a frame-gap reading in wkprobe before the Lane W session.
