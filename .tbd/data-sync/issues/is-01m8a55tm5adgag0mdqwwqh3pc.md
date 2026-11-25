---
type: is
id: is-01m8a55tm5adgag0mdqwwqh3pc
title: "Rendered diff: contiguous added blocks show white gaps between green backgrounds"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T20:08:28.027Z
updated_at: 2026-11-25T20:08:28.027Z
---
In the rendered diff view (PR pages' Docs/rendered view and elsewhere the rendered diff is drawn), added content has a green background, correctly, but white gaps show between consecutive blocks (block margins outside the background). Contiguous added blocks must read as one continuous green band, and the vertical spacing must equal the same content rendered without highlighting.
