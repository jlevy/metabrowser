---
type: is
id: is-01kzst27wr0rapz8yf20mw25w0
title: "Bugbot: reset per-connection error count on reconnect"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzst1xpjmy6yd8kw5gyekcz9
created_at: 2026-08-12T01:40:50.711Z
updated_at: 2026-08-12T01:42:40.650Z
closed_at: 2026-08-12T01:42:40.649Z
close_reason: Validated and fixed. Each newly created EventSource now starts with a fresh consecutive transport-error allowance while exponential backoff remains latched until the 10-second stable timer. Added a regression assertion; make verify passes with 897 tests and 28 golden scenarios.
---
The reconnect timer retains exponential backoff until a stable interval but must reset _esConsecutiveErrors for the newly created EventSource. Otherwise one transient onerror immediately closes the new source after a prior breaker trip.
