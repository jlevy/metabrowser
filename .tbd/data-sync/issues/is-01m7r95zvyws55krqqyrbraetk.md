---
type: is
id: is-01m7r95zvyws55krqqyrbraetk
title: Tree rows cannot be opened from the keyboard, in the file view and a pull request's Rendered diff
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7pfyxz015mfas5phhvtqz33
created_at: 2026-11-18T21:32:07.924Z
updated_at: 2026-11-18T21:32:07.924Z
---
Found by review A13 of PR #557. Rows are divs with a click listener and no tabindex, role or aria-expanded (structured/tree.js renderRowHtml; diff/diff-structured.js mountStructuredDiff). In Rendered every unchanged mapping and list starts closed, and the '… N more' row that draws the next page is a div too, so only a mouse opens them. Fix: make container rows and the more row focusable disclosure buttons in tree.js for both views, with Enter and Space, and pin it in the structured and diff sessions.
