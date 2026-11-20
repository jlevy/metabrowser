---
type: is
id: is-01m7kbg2gkyry2fk74fx0nr2ay
title: "Line totals (+N, −N) meet 4.5:1: --status-success in light and --status-error in dark fall to 2.6–3.7:1 on the page, sidebar, hover and tooltip grounds; consider .diff-stat-add/-del taking --git-status-added/-deleted"
kind: bug
status: open
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-16T23:36:23.312Z
updated_at: 2026-11-20T17:17:43.103Z
---
From #489 review A5 (measured from tokens at 8-bit sRGB). Changes every tree row's and file bar's stats too, so it needs the owner's choice of ink. --git-status-added/-deleted share the hues and measure >= 5.46:1 light, 5.89:1 dark on all four grounds.

## Notes

2026-11-20 audit: absorbs mb-c2li (found by the #555 agent in headless Chrome, closed as a duplicate): in the dark theme the diff line totals' -N (.diff-stat-del, --status-error, no dark override) measure 3.27:1 on --sidebar-bg, below 4.5:1. This is the same ink in the dark case.
