---
type: is
id: is-01kxry268ht7t96d132pjadd8j
title: "Review C5: active_tracker full-inventory scan on loop + quiet_counters unbounded growth"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:05.265Z
updated_at: 2026-07-17T21:16:43.620Z
closed_at: 2026-07-17T21:16:43.620Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
active_tracker.py:141 materializes up to 500K entries on the loop every 5s; quiet_counters never dropped for deleted files (active_tracker.py:179).
