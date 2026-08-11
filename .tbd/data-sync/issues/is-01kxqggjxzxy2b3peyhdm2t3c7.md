---
type: is
id: is-01kxqggjxzxy2b3peyhdm2t3c7
title: Add regression coverage for prompt Ctrl-C server shutdown
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
created_at: 2026-07-17T07:44:02.494Z
updated_at: 2026-07-17T07:52:57.148Z
closed_at: 2026-07-17T07:52:57.148Z
close_reason: Implemented, fully verified, pushed, and green in CI.
---

## Notes

Completed in 651d3e3. Added prompt SSE shutdown, bounded Uvicorn cancellation filtering, and focused normal/error-path tests. make verify and the complete CI matrix pass.
