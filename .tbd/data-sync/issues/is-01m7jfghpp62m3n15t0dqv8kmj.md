---
type: is
id: is-01m7jfghpp62m3n15t0dqv8kmj
title: "QA runbook §5.7 step 10 (label set): match what the page does (#471 review C1)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-16T15:27:18.741Z
updated_at: 2026-11-16T15:27:18.741Z
---
Review C on #471 (C1): docs/qa-v012-repository-library.md step 10's second serve expects no labels-refresh, but the page sends one (200 not_due within 5 min); the first serve's chip can vanish when #465's once-refresh lands. Fix the step's expectations after the stack lands.
