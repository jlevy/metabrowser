---
type: is
id: is-01m1apk29y6cwee6jbhkvnve2h
title: "PR #90 P90-05: A route raising after a 2xx start reports success"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:54.909Z
updated_at: 2026-08-31T01:40:12.925Z
closed_at: 2026-08-31T01:40:12.925Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
When a handler raises mid-stream after http.response.start, the client returns the truncated body with the 2xx status and exit 0, so a partial response looks like a successful one.
