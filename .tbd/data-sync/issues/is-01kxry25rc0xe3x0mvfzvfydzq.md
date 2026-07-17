---
type: is
id: is-01kxry25rc0xe3x0mvfzvfydzq
title: "Review C3: no Host-header validation on local server (DNS rebinding reads files)"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:04.747Z
updated_at: 2026-07-17T21:00:04.747Z
---
Middleware stack is slow-log+gzip only (server.py:2145-2147). Add allowlist middleware (localhost/127.0.0.1/[::1] + bound host) rejecting other Hosts; prerequisite for future mutations.
