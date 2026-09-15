---
type: is
id: is-01m2ha2f0fqry3aphcms2yrwe3
title: Restarting metab with a browser tab open moves to the next port, so the page never reconnects
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-09-15T01:14:30.590Z
updated_at: 2026-09-15T01:46:09.693Z
closed_at: 2026-09-15T01:46:09.693Z
close_reason: "Fixed in PR #127 (merged): local_port_is_free and the remote probe now bind with SO_REUSEADDR, so a stopped server's port is rebound instead of the search moving to the next one. Verified end to end in a headed browser: the page now clears the unreachable error on its own after a restart. Tests fail on the previous implementation (local probe returns False; the generated remote script chose port+1)."
resolution: null
duplicate_of: null
---
The release tells a reader whose server stopped: 'It may have stopped. Start it again with metab <folder>, and this page will reconnect.' With a browser tab open -- which is always, since that tab is who reads the message -- the restarted server binds a different port and the page never reconnects.

Reproduced minimally without a browser: start metab on a port, open one keep-alive connection, stop the server, restart it with the same --port while that connection's socket is still lingering. The restart reports 127.0.0.1:<port+1>. Closing the connection before the restart gives the original port back, which is why a curl-shaped test does not see it.

Cause: server_utils.local_port_is_free binds a probe socket with no SO_REUSEADDR, so a socket in TIME_WAIT from the stopped server's accepted connection makes the port look occupied and find_available_local_port moves on. Uvicorn binds the real listener with SO_REUSEADDR, so the port it rejected was bindable all along: the probe answers a different question from the one the server will ask.

Found by hand-checking the v0.10.0 release's 'not reachable, then automatic recovery' behaviour; the harness's restart landed on port+1 while the page kept polling the original.

Fix: give the probe the same option the real bind uses, with a test that puts a socket in TIME_WAIT on the port and asserts the probe still calls it free.
