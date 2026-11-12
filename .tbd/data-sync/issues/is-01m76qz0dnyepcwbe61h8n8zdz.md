---
type: is
id: is-01m76qz0dnyepcwbe61h8n8zdz
title: "PR #361 B1: an automatically found uv can run another account s code"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76qyxmt9sy6zr9ffwqe0eqs
hold: null
hold_until: null
created_at: 2026-11-12T02:04:07.988Z
updated_at: 2026-11-12T03:38:23.872Z
started_at: 2026-11-12T02:04:21.834Z
closed_at: 2026-11-12T03:38:23.848Z
close_reason: "Fixed in f58eb702: ExecutableTrust on the uv the app runs (B1); ExecutableTrustTests, SetupGuideTests. Metab discovery has no such check (escalated)."
resolution: null
duplicate_of: null
---
High. AppDelegate.swift:461, Runtime.swift:116 (isExecutableFile checks no ownership). Review B1: https://github.com/jlevy/metabrowser/pull/361
