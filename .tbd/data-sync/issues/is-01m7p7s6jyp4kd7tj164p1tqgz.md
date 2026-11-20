---
type: is
id: is-01m7p7s6jyp4kd7tj164p1tqgz
title: Process group for the server's other asyncio children (#527 D1 follow-up)
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wyspfffhwcfcze4mke8jjp
created_at: 2026-11-18T02:29:11.389Z
updated_at: 2026-11-20T17:16:25.470Z
---
Deferred from PR #527 D1: a pin's git cat-file --batch readers share the server's group; also file the CPython 3.14.7 waitid behaviour upstream.
