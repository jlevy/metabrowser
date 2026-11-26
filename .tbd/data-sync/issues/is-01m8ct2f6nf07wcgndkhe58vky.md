---
type: is
id: is-01m8ct2f6nf07wcgndkhe58vky
title: Keep refresh changes within the shell startup transfer limit
kind: bug
status: in_progress
priority: 2
version: 2
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq09w7xhakmpz486762491
hold: null
hold_until: null
created_at: 2026-11-26T20:52:06.993Z
updated_at: 2026-11-26T20:52:08.758Z
started_at: 2026-11-26T20:52:08.751Z
---
Exact CI reported the eager shell 629 compressed bytes over the 220 KiB startup cap. Preserve refresh behavior and the cap, shifting work out of startup where appropriate.
