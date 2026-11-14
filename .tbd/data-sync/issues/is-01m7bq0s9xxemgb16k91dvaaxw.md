---
type: is
id: is-01m7bq0s9xxemgb16k91dvaaxw
title: "Pull cores: a visible demand gets busy while a background core job runs"
kind: task
status: closed
priority: 2
version: 3
labels: []
dependencies: []
created_at: 2026-11-14T00:23:49.819Z
updated_at: 2026-11-14T09:23:08.404Z
closed_at: 2026-11-14T09:23:08.403Z
close_reason: "Merged in #421: a visible core demand preempts a running background batch (lane field; cancel, await, recheck failure hold and busy, then admit); overlap checked against rows actually being read; background leases kept."
resolution: null
duplicate_of: null
---
Found while fixing mb-z5kx (#414). The server runs one optional core job per source, so a visible pull-cores demand that arrives while a background job is running answers `busy` until that job ends. #414 removed the client-side wait (a visible demand aborts the background request), but the server-side job still blocks the visible one.

Done when a visible demand preempts or runs beside a background core job on the server (cancelling the background job at a safe point, or a separate visible slot), measured, with a test.
