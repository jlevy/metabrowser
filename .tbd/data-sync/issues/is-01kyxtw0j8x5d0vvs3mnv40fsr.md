---
type: is
id: is-01kyxtw0j8x5d0vvs3mnv40fsr
title: Mark the Uvicorn handle_exit override explicitly
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kyxtvry05tmsdc00pabw5n33
created_at: 2026-08-01T04:56:11.079Z
updated_at: 2026-08-01T04:56:11.079Z
---
The new _QuietForceExitServer.handle_exit method overrides uvicorn.Server.handle_exit. Apply the repository Python guideline by adding typing.override so upstream signature drift is checked.
