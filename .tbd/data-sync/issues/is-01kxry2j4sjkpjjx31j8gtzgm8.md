---
type: is
id: is-01kxry2j4sjkpjjx31j8gtzgm8
title: "Review C11: applyCellPatch attribute-selector escaping incomplete (app.js:3574)"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:17.433Z
updated_at: 2026-07-17T21:16:43.646Z
closed_at: 2026-07-17T21:16:43.646Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Only double quotes escaped when building [data-path] selector; use CSS.escape.
