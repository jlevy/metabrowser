---
type: is
id: is-01m8ct2f6nf07wcgndkhe58vky
title: Keep refresh changes within the shell startup transfer limit
kind: bug
status: closed
priority: 2
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cq09w7xhakmpz486762491
hold: null
hold_until: null
created_at: 2026-11-26T20:52:06.993Z
updated_at: 2026-11-26T21:21:45.834Z
started_at: 2026-11-26T20:52:08.751Z
closed_at: 2026-11-26T21:21:45.832Z
close_reason: "Implemented and independently reviewed in merged Metabrowser PR #893. Exact-head CI passed, and the live refresh timing matched the event log."
resolution: null
duplicate_of: null
---
Exact CI reported the eager shell 629 compressed bytes over the 220 KiB startup cap. Preserve refresh behavior and the cap, shifting work out of startup where appropriate.
