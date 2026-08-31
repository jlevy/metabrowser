---
type: is
id: is-01m1cdvrb0jx9bk0e8rdp66q6t
title: "PR #90 CODE-03: Lifespan shutdown had the same dead-path bug startup was fixed for"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:51.295Z
updated_at: 2026-08-31T17:28:51.295Z
---
__aexit__ drained the task before checking the message, so the app's traceback escaped instead of the failure reason. No timeout either.
