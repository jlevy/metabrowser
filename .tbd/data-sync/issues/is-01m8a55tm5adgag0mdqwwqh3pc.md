---
type: is
id: is-01m8a55tm5adgag0mdqwwqh3pc
title: "Rendered diff: contiguous added blocks show white gaps between green backgrounds"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-25T20:08:28.027Z
updated_at: 2026-11-25T22:25:46.627Z
started_at: 2026-11-25T20:16:46.487Z
closed_at: 2026-11-25T22:25:46.626Z
close_reason: "Merged in stack #846 (main 1cfd383d3)"
resolution: null
duplicate_of: null
---
In the rendered diff view (PR pages' Docs/rendered view and elsewhere the rendered diff is drawn), added content has a green background, correctly, but white gaps show between consecutive blocks (block margins outside the background). Contiguous added blocks must read as one continuous green band, and the vertical spacing must equal the same content rendered without highlighting.
