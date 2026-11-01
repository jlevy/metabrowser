---
type: is
id: is-01m6c49c5na05re5tz31r2njdx
title: A large file paints its top before scrolling to its line anchor
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:00.948Z
updated_at: 2026-11-01T18:00:00.948Z
---
Measured 2026-11-01 in headless Chrome: for 40,000 lines the reveal comes 181-215 ms after commit, because the fragment event waits on measureNextPaint at app.js near line 6120. In a hidden page rAF never runs, so it waits until the page is shown. Delivering the fragment before the paint wait would likely remove both; not tried. A wheel scroll in the gap was not yanked (9 of 9).
