---
type: is
id: is-01m8501z5hf5rvhsst744a0beq
title: Treemap folder labels max out at a normal text size
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
created_at: 2026-11-23T20:02:46.576Z
updated_at: 2026-11-23T20:02:56.779Z
started_at: 2026-11-23T20:02:56.777Z
---
Requested in manual testing: folder labels grow with their cell up to TYPOGRAPHY_DEFAULTS.labelMaxPx (24 px) in treemap-layout.js, so large folders shout. Cap a folder's label at a normal size; files keep the fluid scale.
