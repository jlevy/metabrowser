---
type: is
id: is-01kxry2hwpbm83pyx8f3r5w77q
title: "Review C10: SDK wrapWithCopy emits inline onclick bound to private app.js global (plugin_sdk.js:666-678)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:17.174Z
updated_at: 2026-07-17T21:00:17.174Z
---
Violates SDK boundary and blocks CSP; replace with delegated listener owned by the SDK. Feeds existing CSP bead.
