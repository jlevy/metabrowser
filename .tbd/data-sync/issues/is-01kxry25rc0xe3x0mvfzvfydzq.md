---
type: is
id: is-01kxry25rc0xe3x0mvfzvfydzq
title: "Review C3: no Host-header validation on local server (DNS rebinding reads files)"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:04.747Z
updated_at: 2026-07-17T21:16:43.611Z
closed_at: 2026-07-17T21:16:43.611Z
close_reason: "Fixed in the review-fixes PR (branch claude/metabrowser-senior-review-yw44vt): event-loop stat offloads, sidekick threadpool, Host validation middleware + tests, active-tracker scan/counters, mtime-cache lock + new tests, SRI on CDN assets + enforcement test, selectFile abort + bounded maps, SSE circuit breaker, esc() regex, delegated copy handler, selector escaping. make verify green: 716 passed."
---
Middleware stack is slow-log+gzip only (server.py:2145-2147). Add allowlist middleware (localhost/127.0.0.1/[::1] + bound host) rejecting other Hosts; prerequisite for future mutations.
