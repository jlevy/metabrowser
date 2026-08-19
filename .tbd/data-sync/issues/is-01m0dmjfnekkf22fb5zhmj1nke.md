---
type: is
id: is-01m0dmjfnekkf22fb5zhmj1nke
title: "Diff view: syntax highlighting by layer, added files first"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T18:29:40.141Z
updated_at: 2026-08-19T18:29:40.141Z
---
Design layer over the diff view, informed by the research appendix (highlight-then-diff vs diff-then-highlight across GitHub, Monaco, delta, difftastic). Phase order: (1) Added whole files get full, clean syntax highlighting with an added indicator that does not fight the lexer — status-success left bar plus a very light status-success background wash; deleted files the mirror. (2) Mixed hunks: highlighting is messier and may not pay below a size threshold — measure before bounding, decide per research. (3) Per-file small subtle tabs on each file section: inline view now, Rendered view for Markdown — the per-file expression of the spec's view-phasing table. Keep add/del tints and intraline emphasis legible under highlighting. Related: mb-hhmb keeps split view, intraline, and context expansion; highlighting itself lives here.
