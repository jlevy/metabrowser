---
type: is
id: is-01m03tttegsetfapn6622t3w1c
title: Require both section count and document length before showing Markdown TOC
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m03tqjzm7j6qkxjeath5qe0d
created_at: 2026-08-15T23:06:40.450Z
updated_at: 2026-08-16T02:21:05.154Z
closed_at: 2026-08-16T02:21:05.154Z
close_reason: null
---
Short one-page docs with several sections currently still get a table of contents. The TOC should require BOTH: (1) enough sections (roughly the current cutoff, ~7-8), and (2) sufficient document length (at least a page, likely closer to two pages). Investigate whether the TOC-inclusion decision is baked into kpress; if so fix it at the kpress level, otherwise fix in MetaBrowser.
