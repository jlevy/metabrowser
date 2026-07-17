---
type: is
id: is-01kxry2hcrfj96hxrk5zetpg14
title: "Review C8: shell EventSource reconnects with no backoff (app.js:3753-3758)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:16.664Z
updated_at: 2026-07-17T21:00:16.664Z
---
Browser-native ~3s retry forever while server is down; add manual reconnect with exponential backoff.
