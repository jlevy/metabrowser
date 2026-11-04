---
type: is
id: is-01m6j5mzwzjd6xx8bpwxvcpfbb
title: Make the gh timeout child-cleanup fixture wait for readiness
kind: bug
status: in_progress
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-04T02:19:16.762Z
updated_at: 2026-11-04T02:28:26.999Z
---
The exact 224e32aa full verification run reported the expected one-second GhError timeout, then failed reading the child PID marker because the fake gh had not yet spawned its child on the loaded external filesystem. Preserve the real timeout and parent/child cleanup assertions, add bounded fixture readiness with deterministic delayed startup, and keep product code unchanged. Evidence: make-verify-224e32aa.log; 4724 passed, 9 expected skips, one fixture failure.

## Notes

Forward commit14433032 adds readiness handshake before unchanged one-second production finish timeout. Author22provider tests plus Make lint/type/parity gates passed; original delayed-start and no-cleanup negative controls fail as expected. Root and independent reviewer read full fixture/production path: clean. Product source remains exact224; final fifth-layer full gate will cover aggregate.
