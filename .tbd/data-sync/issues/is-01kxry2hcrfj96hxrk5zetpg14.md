---
type: is
id: is-01kxry2hcrfj96hxrk5zetpg14
title: "Review C8: shell EventSource reconnects with no backoff (app.js:3753-3758)"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.664Z
updated_at: 2026-07-17T21:16:43.634Z
closed_at: 2026-07-17T21:16:43.634Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Browser-native ~3s retry forever while server is down; add manual reconnect with exponential backoff.
