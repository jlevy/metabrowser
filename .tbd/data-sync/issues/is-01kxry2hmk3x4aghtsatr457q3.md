---
type: is
id: is-01kxry2hmk3x4aghtsatr457q3
title: "Review C9: duplicate divergent HTML escaping (app.js:108 esc via DOM vs plugin_sdk.js:129 regex)"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.915Z
updated_at: 2026-07-17T21:16:43.637Z
closed_at: 2026-07-17T21:16:43.637Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
esc() creates a DOM element per call in tree hot loops; converge on the regex implementation.
