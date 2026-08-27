---
type: is
id: is-01m11y0pdf35eeyrvg2gvpjq71
title: Inventory boot-walk summary logs at INFO on every start
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-27T15:39:31.630Z
updated_at: 2026-08-27T15:39:31.630Z
---
'inventory walker complete: status=done files=3 entries=6 elapsed=8ms' prints on every metab invocation. Routine lifecycle belongs at DEBUG per the policy stated in server.py's perf-logging setup; reserve INFO for the notable outcomes (truncated index, or a walk slower than SLOW_OPERATION_LOG_SECONDS) where the terminal line tells the user something about what they are browsing.
