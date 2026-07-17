---
type: is
id: is-01kxry2h4gqem5a299efyptpp6
title: "Review C7: app.js selectFile lacks AbortController; fileETags/fileNeedsRevalidate unbounded"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.399Z
updated_at: 2026-07-17T21:16:43.629Z
closed_at: 2026-07-17T21:16:43.629Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
app.js:2408 superseded fetches run to completion; ETag/revalidate maps grow without bound in long sessions (fileCache LRU only bounds the 30-entry cache).
