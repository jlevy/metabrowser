---
type: is
id: is-01m8a7vvp0b3jw67ry6yamx8dn
title: "Rendered diff: an edited table's two bands overlap, and Current sits 20-26 px high after a table"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T20:55:27.156Z
updated_at: 2026-11-25T20:55:27.156Z
---
Found while fixing mb-zkmy (PR #851). withoutRenderWrappers in static/inert-html.js strips .kpress-table-wrap, so an edited table's removed and added bands overlap by 8 px (before and after #851), and in the mixed fixture the Current view sits 20-26 px above the Document view after a table. Fix by construction: keep the table wrapper (or its spacing) in the diff's rendering so tables take the same spacing as the Document view.
