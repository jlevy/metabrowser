---
type: is
id: is-01m84g9wsvvha2tdrh2mpv2vkr
title: "Guided PR: center the arrows in the step list's icon buttons"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7x3g8rdhbeh7f0j0j7nz4sq
hold: null
hold_until: null
created_at: 2026-11-23T15:27:29.075Z
updated_at: 2026-11-23T16:13:12.336Z
started_at: 2026-11-23T15:27:45.450Z
closed_at: 2026-11-23T16:13:12.334Z
close_reason: "Done in PR #677 (84665dd8e)"
resolution: null
duplicate_of: null
---
The icon-only arrow buttons hold an empty label span, and the flex gap pushes the arrow off center. Build those buttons without the label.
