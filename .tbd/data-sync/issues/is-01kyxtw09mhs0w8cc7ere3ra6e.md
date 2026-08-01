---
type: is
id: is-01kyxtw09mhs0w8cc7ere3ra6e
title: Restore Uvicorn logger state after forced server exit
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kyxtvry05tmsdc00pabw5n33
created_at: 2026-08-01T04:56:10.803Z
updated_at: 2026-08-01T05:00:41.533Z
closed_at: 2026-08-01T05:00:41.532Z
close_reason: "Fixed in 1d4f8ae: run_serve preserves and restores the process-global uvicorn.error logger level for both normal forced-exit return and exceptions; parameterized regression coverage exercises both paths."
---
PR #15 raises the process-global uvicorn.error logger to CRITICAL on a forced second Ctrl-C but run_serve only removes its filter. Restore the prior level in the outer finally path and cover both forced and exceptional returns so later in-process server runs are not silently suppressed.
