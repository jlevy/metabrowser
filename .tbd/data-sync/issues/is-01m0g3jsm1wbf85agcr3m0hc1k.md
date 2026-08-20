---
type: is
id: is-01m0g3jsm1wbf85agcr3m0hc1k
title: Loading failures and overruns always console.error with full details
kind: feature
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-20T17:30:27.840Z
updated_at: 2026-08-20T17:41:04.532Z
closed_at: 2026-08-20T17:41:04.531Z
close_reason: "Landed in 88ceab8: view loads, per-file hydration, and container children all console.error with request/hook/elapsed/error, and hydration warns past a 4s overrun even when it later succeeds."
---
Any progress state that fails or exceeds its expected timeframe must console.error with full details (what was requested, the route/hook, elapsed ms, the error object), so a stall is diagnosable from the console alone rather than silently spinning. Start with the diff view's loaders (comparison, deferred file, container children) and give them an explicit slow-threshold warning; consider a shared helper so every surface reports the same shape.
