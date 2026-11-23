---
type: is
id: is-01m83gjnp5sqwgd06n63gp428m
title: A Markdown render's start wait ignores METABROWSER_INERT_RENDER_DEADLINE_MS, so pull-markdown answers 503 after 5 s on a loaded machine
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T06:13:02.276Z
updated_at: 2026-11-23T06:36:30.154Z
started_at: 2026-11-23T06:36:30.096Z
---
Found while building the update-cadence Phase 2: diff/markdown_projection_worker.py waits _START_WAIT_S for the Markdown child to become ready, fixed at INERT_RENDER_DEADLINE_MS / 1000 (5 s). A cold start took 1.36 s at load 16 and passes 5 s at load 300 to 400, so pull-markdown answers renderer_unavailable (503) after 5.1 to 8.3 s. METABROWSER_INERT_RENDER_DEADLINE_MS does not lengthen the start wait because it reads the constant. Measure the cold start's shape and set the start wait from it (or read the setting), with a test.
