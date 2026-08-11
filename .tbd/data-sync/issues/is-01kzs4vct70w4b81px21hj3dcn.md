---
type: is
id: is-01kzs4vct70w4b81px21hj3dcn
title: SSE queue overflow can silently stale live browser state
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T19:30:06.278Z
updated_at: 2026-08-11T19:42:08.223Z
closed_at: 2026-08-11T19:42:08.222Z
close_reason: Fixed and validated on the v0.3.0 release branch; live state now self-heals after bounded queue overflow.
---
When an inventory subscriber queue or per-browser SSE queue fills, the current code removes it from fan-out but does not close the active StreamingResponse. The browser continues receiving local heartbeats while no longer receiving filesystem events. Inventory-bus resubscription also resumes after an event gap without resetting replay state or forcing connected clients to take a fresh snapshot. Reproduce/observe on a large home-directory scan as repeated queue-full and resubscribe warnings. Make both overflow paths explicitly self-healing, preserve bounded queues, avoid warning spam, and test the recovery contract before v0.3.0.

## Notes

Confirmed release-blocking correctness defect. Inventory overflow removed its subscriber, while the SSE bus removed per-browser queues without ending their StreamingResponse; affected browsers could keep receiving heartbeats while silently stale. Fixed bounded backpressure at both layers: stale queue contents are replaced by fs.resync_required, the bus clears and detaches affected connection queues, the SSE stream delivers the marker and ends, and the browser reconnects immediately for a fresh scoped snapshot. Routine inventory overflow detail is DEBUG; the single user-visible warning states that browser connections are being refreshed. Added inventory, event-bus, stream-termination, and browser-reconnect tests. Full make verify passes with 877 pytest tests and 28 CLI golden scenarios.
