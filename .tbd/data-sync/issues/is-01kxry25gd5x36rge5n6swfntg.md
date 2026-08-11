---
type: is
id: is-01kxry25gd5x36rge5n6swfntg
title: "Review C2: data-hook dispatcher runs sync sidekicks on the event loop (static_assets.py:147)"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:04.493Z
updated_at: 2026-07-17T21:16:43.606Z
closed_at: 2026-07-17T21:16:43.606Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Async handler calls sidekick(request) inline, so sync hooks (e.g. structured 8MiB parse) stall the loop; Starlette's own sync-endpoint path uses run_in_threadpool. Offload non-coroutine sidekicks.
