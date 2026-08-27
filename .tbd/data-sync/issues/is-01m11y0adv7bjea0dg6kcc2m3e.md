---
type: is
id: is-01m11y0adv7bjea0dg6kcc2m3e
title: "Serve mode: repeat Ctrl-C leaks a shutdown traceback and a nondeterministic exit code"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-27T15:39:19.353Z
updated_at: 2026-08-27T16:04:27.344Z
closed_at: 2026-08-27T16:04:27.329Z
close_reason: "Serve mode holds SIGINT at SIG_IGN across uvicorn's run, so uvicorn's capture_signals re-raise is a no-op and no repeat Ctrl-C can land on Python's default handler during exit. Server.interrupted is now the live signal for exit 130. First interrupt writes 'Stopping Metabrowser.' to fd 2 from the handler (raw os.write, no stdio lock). Verified: three SIGINTs at gaps 0.0-0.6s all give rc=130 with no traceback, and a single Ctrl-C under uvx is clean."
resolution: null
duplicate_of: null
---
Uvicorn 0.49 capture_signals restores the previous SIGINT handler when Server.run() returns and then re-raises the captured signal. Between that restore and process exit (~250 ms) a repeat Ctrl-C lands on Python's default handler:

- ~0.1-0.2 s after the first: KeyboardInterrupt inside threading._shutdown (an AnyIO worker thread is non-daemon), printing 'Exception ignored on threading shutdown' with a traceback.
- ~0.2 s after: the process dies from the signal, exit -2 instead of 130.

Reproduced with .venv/bin/metab and two SIGINTs at controlled gaps, and with a single terminal Ctrl-C under 'uvx metabrowser@latest' (uv forwards a duplicate).

Also: because uvicorn re-raises SIGINT, the existing 'if uvicorn_server.interrupted' -> typer.Exit(130) path in run_serve never executes for a real interrupt; the 130 comes from entrypoint.main()'s KeyboardInterrupt catch.
