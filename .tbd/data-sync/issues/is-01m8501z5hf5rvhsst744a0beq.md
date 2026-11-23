---
type: is
id: is-01m8501z5hf5rvhsst744a0beq
title: Treemap folder labels max out at a normal text size
kind: task
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/764
    at: 2026-11-23T20:35:16.190Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82yzrw40w07dnw6zhsg8jep
hold: null
hold_until: null
created_at: 2026-11-23T20:02:46.576Z
updated_at: 2026-11-23T20:35:18.636Z
started_at: 2026-11-23T20:02:56.777Z
closed_at: 2026-11-23T20:35:18.633Z
close_reason: "Done in PR #764 (layer 8 of stack #725)"
resolution: null
duplicate_of: null
---
Requested in manual testing: folder labels grow with their cell up to TYPOGRAPHY_DEFAULTS.labelMaxPx (24 px) in treemap-layout.js, so large folders shout. Cap a folder's label at a normal size; files keep the fluid scale.
