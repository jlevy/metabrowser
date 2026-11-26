---
type: is
id: is-01m8cfga56s2tdtzhedrrdw604
title: A stack's rendered-diff request reads the stack twice, outside any timed phase
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T17:47:26.244Z
updated_at: 2026-11-26T17:47:29.066Z
started_at: 2026-11-26T17:47:29.063Z
---
Measured for mb-3dkn: on /stack/<n>/changes each file's pull-rendered-diff request read the stack in admission and again in the handler, 21-57 ms and 21-55 ms at load ~230, before the cache was consulted, and neither was a Server-Timing phase, so ~95 ms per request was unattributed in the app's log.
