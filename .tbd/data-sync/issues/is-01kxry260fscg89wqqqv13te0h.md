---
type: is
id: is-01kxry260fscg89wqqqv13te0h
title: "Review C4: watch_backends.py:264 second sync stat (is_dir) on event loop per watcher event"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.007Z
updated_at: 2026-07-17T21:16:43.616Z
closed_at: 2026-07-17T21:16:43.616Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Reuse the threaded lstat result (S_ISDIR of st_mode) instead of a second synchronous Path.is_dir() stat.
