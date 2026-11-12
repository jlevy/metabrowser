---
type: is
id: is-01m77dgvyzmpbjgd7gqnp96998
title: "Review D3 on #363: a malformed request ends the gate outside its cleanup"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
hold: null
hold_until: null
created_at: 2026-11-12T08:20:53.342Z
updated_at: 2026-11-12T08:21:07.974Z
started_at: 2026-11-12T08:21:07.973Z
---
A request for /% threw URIError from decodeURIComponent inside the request callback, and a filesystem or read-stream error did the same, so the harness exited outside main()'s finally and could leave Chrome running. Answer such requests with an error response, and tie Chrome's lifetime to the harness through the run's Cleanup on an uncaught exception.
