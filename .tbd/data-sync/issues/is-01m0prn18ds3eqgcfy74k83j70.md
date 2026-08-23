---
type: is
id: is-01m0prn18ds3eqgcfy74k83j70
title: "PR #72 review R6: tree_region_repaints and render_spans are the same number twice"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:07.884Z
updated_at: 2026-08-23T07:34:07.884Z
---
probe.js:251 and :256 are both renderSpans.length, and both are in run.py METRICS, so compare prints one value under two headings. renderSpans at probe.js:81 already filters to renderTreeNodes*, so the two are the same set by construction. Fix: keep one name.
