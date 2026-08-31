---
type: is
id: is-01m1apk1za6n47w0naqm8qmwkz
title: "PR #90 P90-04: Lifespan startup failure raises a traceback, not CLIError"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:54.569Z
updated_at: 2026-08-31T01:22:54.569Z
---
Starlette re-raises through _finish_lifespan_task before the intended CLIError path runs, so the error branch is dead code and users get a traceback. Also an unbounded hang if no failure message arrives.
