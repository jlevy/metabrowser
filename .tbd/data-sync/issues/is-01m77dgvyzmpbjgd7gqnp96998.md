---
type: is
id: is-01m77dgvyzmpbjgd7gqnp96998
title: "Review D3 on #363: a malformed request ends the gate outside its cleanup"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:20:53.342Z
updated_at: 2026-11-12T08:32:42.317Z
started_at: 2026-11-12T08:21:07.973Z
closed_at: 2026-11-12T08:32:42.316Z
close_reason: "Fixed in 6274750e and 2d2171fa (#363): request failures become error responses; Chrome and webkit-driver are owned by the run's Cleanup, which cleanUpBeforeExit runs on an uncaught exception or a signal."
resolution: null
duplicate_of: null
---
A request for /% threw URIError from decodeURIComponent inside the request callback, and a filesystem or read-stream error did the same, so the harness exited outside main()'s finally and could leave Chrome running. Answer such requests with an error response, and tie Chrome's lifetime to the harness through the run's Cleanup on an uncaught exception.
