---
type: is
id: is-01kytdw74vrhpcsy83rfadr43x
title: Ctrl-C double-press still prints lifespan CancelledError traceback
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-07-30T21:11:23.031Z
updated_at: 2026-07-30T21:49:30.198Z
closed_at: 2026-07-30T21:49:30.190Z
close_reason: "Fixed in claude/quiet-force-exit-shutdown: _QuietForceExitServer silences uvicorn.error on force_exit"
---
On force exit (^C^C), uvicorn's lifespan task is cancelled before shutdown completes. Starlette formats the CancelledError/KeyboardInterrupt traceback as text and sends it via lifespan.shutdown.failed; uvicorn logs it with logger.error(message) and no exc_info, so _shutdown_noise_filter in cli/serve.py (which matches on exc_info) does not drop it. Fix: also match the pre-formatted traceback text form.
