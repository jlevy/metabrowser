---
type: is
id: is-01m7p7s6jyp4kd7tj164p1tqgz
title: Process group for the server's other asyncio children (#527 D1 follow-up)
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m75fzpspek15x7d5dqhnc2yw
created_at: 2026-11-18T02:29:11.389Z
updated_at: 2026-11-18T02:29:11.389Z
---
Deferred from PR #527 D1: a pin's git cat-file --batch readers share the server's group; also file the CPython 3.14.7 waitid behaviour upstream.
