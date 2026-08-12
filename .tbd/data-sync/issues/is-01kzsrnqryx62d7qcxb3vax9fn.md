---
type: is
id: is-01kzsrnqryx62d7qcxb3vax9fn
title: "PR #30 review R5: back off resync-driven reconnects"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:32.413Z
updated_at: 2026-08-12T01:33:14.592Z
closed_at: 2026-08-12T01:33:14.592Z
close_reason: Implemented shared exponential backoff for error- and resync-driven reconnects; reset occurs only after a 10-second stable connection.
---
PR #30 senior review R5, app.js:4797-4812. Load-triggered resync closes and reconnects synchronously while resetting the circuit breaker, allowing sustained queue overflow to cause a reconnect/snapshot storm.
