---
type: is
id: is-01kxry2hwpbm83pyx8f3r5w77q
title: "Review C10: SDK wrapWithCopy emits inline onclick bound to private app.js global (plugin_sdk.js:666-678)"
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:17.174Z
updated_at: 2026-07-17T21:16:43.641Z
closed_at: 2026-07-17T21:16:43.641Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Violates SDK boundary and blocks CSP; replace with delegated listener owned by the SDK. Feeds existing CSP bead.
