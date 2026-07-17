---
type: is
id: is-01kxry257vj8jqy8cy82bv7hqf
title: "Review C1: sse.py:153 sync stat() on event loop every 500ms per tailed file"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:04.219Z
updated_at: 2026-07-17T21:16:43.590Z
closed_at: 2026-07-17T21:16:43.590Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Wrap the poll-cycle stat in asyncio.to_thread; the read at sse.py:175 is already threaded.
