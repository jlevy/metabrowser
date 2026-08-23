---
type: is
id: is-01m0prn85fh4jzkwpcezhmfkqy
title: "PR #72 review R9: probe.js hardcodes a copy of treeSummaryHtml's pending markup"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:14.958Z
updated_at: 2026-08-23T08:07:31.521Z
closed_at: 2026-08-23T08:07:31.520Z
close_reason: Fixed in 02c3105. The stand-in is built by calling treeSummaryHtml(null, null, null) rather than restating its markup, and is no longer a clone of the settled row, so it does not inherit tree-summary-split.
---
probe.js:193-196 restates the pending row as two bare spans; app.js:998-1003 emits them wrapping countHtml(null)/sizeHtml(null), i.e. .tally-pending inline-blocks. Separately cloneNode(false) keeps tree-summary-split, which the comment says the pending row never has. Neither changes today's 23px, both are undefended coupling. Fix: derive the markup from the app and strip the split class from the clone.
