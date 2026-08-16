---
type: is
id: is-01kxry31tw40txkbzctzv1mtsd
title: "Platform A5: repo-scoped plugin surface — [[tool]] mount point for non-file views"
kind: feature
status: open
priority: 1
version: 4
labels: []
dependencies:
  - type: blocks
    target: is-01kxse0vt4cyng7mvtr3hk2rct
parent_id: is-01kxry18kdjj6xk8nkz4bs4ba6
created_at: 2026-07-17T21:00:33.500Z
updated_at: 2026-08-16T08:06:17.779Z
extensions:
  linear:
    id: 28ee38a5-1006-44dd-a6a0-814e434a8190
    linked_at: 2026-08-16T08:06:17.779Z
---
Views bind to file kinds; /api/file rejects directories (server.py:1130). A diff/review surface needs a shell-level tool mount; container/directory kinds are the longer-term generalization (aligns with archive roadmap).
