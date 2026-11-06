---
type: is
id: is-01m6shhp93hj2aybfj68g5prxh
title: Verify PR watch updates, disconnects, and reconnects
kind: task
status: in_progress
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6shhkwxasd5rpv91y17qc4w
hold: null
hold_until: null
created_at: 2026-11-06T23:01:52.546Z
updated_at: 2026-11-06T23:49:13.666Z
started_at: 2026-11-06T23:03:25.395Z
---
Verify new and edited PRs and status changes, disconnected and restored networking, absent or unauthenticated gh, rate limiting, and cached use in both source modes with focused sessions and a manual browser playbook.

## Notes

Built-in browser verified cached rows during GitHub and local-server disconnections, followed by automatic recovery and a newly opened and closed/retitled PR. A separate PATH without gh verified setup guidance and Reload. The managed public repository used real gh. Fake CLI and browserless sessions cover auth and rate-limit behavior.
