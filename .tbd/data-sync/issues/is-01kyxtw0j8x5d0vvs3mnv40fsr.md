---
type: is
id: is-01kyxtw0j8x5d0vvs3mnv40fsr
title: Mark the Uvicorn handle_exit override explicitly
kind: task
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01kyxtvry05tmsdc00pabw5n33
created_at: 2026-08-01T04:56:11.079Z
updated_at: 2026-08-01T05:00:41.806Z
closed_at: 2026-08-01T05:00:41.804Z
close_reason: "Fixed in 1d4f8ae: _QuietForceExitServer.handle_exit is marked with typing.override, pinning the Uvicorn method contract under strict type checking."
---
The new _QuietForceExitServer.handle_exit method overrides uvicorn.Server.handle_exit. Apply the repository Python guideline by adding typing.override so upstream signature drift is checked.
