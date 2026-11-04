---
type: is
id: is-01m6j5mzwzjd6xx8bpwxvcpfbb
title: Make the gh timeout child-cleanup fixture wait for readiness
kind: bug
status: closed
priority: 2
version: 5
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-04T02:19:16.762Z
updated_at: 2026-11-04T17:14:29.885Z
closed_at: 2026-11-04T17:14:29.885Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
The exact 224e32aa full verification run reported the expected one-second GhError timeout, then failed reading the child PID marker because the fake gh had not yet spawned its child on the loaded external filesystem. Preserve the real timeout and parent/child cleanup assertions, add bounded fixture readiness with deterministic delayed startup, and keep product code unchanged. Evidence: make-verify-224e32aa.log; 4724 passed, 9 expected skips, one fixture failure.

## Notes

Forward commit14433032 adds readiness handshake before unchanged one-second production finish timeout. Author22provider tests plus Make lint/type/parity gates passed; original delayed-start and no-cleanup negative controls fail as expected. Root and independent reviewer read full fixture/production path: clean. Product source remains exact224; final fifth-layer full gate will cover aggregate.
