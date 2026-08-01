---
type: is
id: is-01kyxtw09mhs0w8cc7ere3ra6e
title: Restore Uvicorn logger state after forced server exit
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kyxtvry05tmsdc00pabw5n33
created_at: 2026-08-01T04:56:10.803Z
updated_at: 2026-08-01T04:56:10.803Z
---
PR #15 raises the process-global uvicorn.error logger to CRITICAL on a forced second Ctrl-C but run_serve only removes its filter. Restore the prior level in the outer finally path and cover both forced and exceptional returns so later in-process server runs are not silently suppressed.
