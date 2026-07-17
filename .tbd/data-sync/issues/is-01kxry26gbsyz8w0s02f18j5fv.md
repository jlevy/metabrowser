---
type: is
id: is-01kxry26gbsyz8w0s02f18j5fv
title: "Review C6: mtime_cache holds lock across os.stat and deep-copies every hit; no dedicated test file"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.515Z
updated_at: 2026-07-17T21:16:43.625Z
closed_at: 2026-07-17T21:16:43.625Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
mtime_cache.py:93-110: two-phase stat outside lock; deepcopy cost noted; add tests/test_mtime_cache.py covering hit/miss/absent.
