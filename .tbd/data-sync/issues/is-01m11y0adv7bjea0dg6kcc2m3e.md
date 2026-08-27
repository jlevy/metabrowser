---
type: is
id: is-01m11y0adv7bjea0dg6kcc2m3e
title: "Serve mode: repeat Ctrl-C leaks a shutdown traceback and a nondeterministic exit code"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-27T15:39:19.353Z
updated_at: 2026-08-27T15:39:19.353Z
---
Uvicorn 0.49 capture_signals restores the previous SIGINT handler when Server.run() returns and then re-raises the captured signal. Between that restore and process exit (~250 ms) a repeat Ctrl-C lands on Python's default handler:

- ~0.1-0.2 s after the first: KeyboardInterrupt inside threading._shutdown (an AnyIO worker thread is non-daemon), printing 'Exception ignored on threading shutdown' with a traceback.
- ~0.2 s after: the process dies from the signal, exit -2 instead of 130.

Reproduced with .venv/bin/metab and two SIGINTs at controlled gaps, and with a single terminal Ctrl-C under 'uvx metabrowser@latest' (uv forwards a duplicate).

Also: because uvicorn re-raises SIGINT, the existing 'if uvicorn_server.interrupted' -> typer.Exit(130) path in run_serve never executes for a real interrupt; the 130 comes from entrypoint.main()'s KeyboardInterrupt catch.
