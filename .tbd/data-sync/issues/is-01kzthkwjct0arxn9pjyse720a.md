---
type: is
id: is-01kzthkwjct0arxn9pjyse720a
title: Fix Quick File convergence after reconnect during an incomplete inventory
kind: bug
status: closed
priority: 1
version: 4
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-12T08:32:26.187Z
updated_at: 2026-08-12T09:04:54.381Z
closed_at: 2026-08-12T09:04:54.380Z
close_reason: Implemented with regression coverage; full make verify passed on 2026-08-12.
---

## Notes

EventSource opens now force a continuity refetch, invalidate an in-flight pre-reconnect bulk response, and suppress only the paired sentinel fetch. Completion after a partial reconnect payload waits for an authoritative catalog response. DOM regressions cover both reconnect during scanning and reconnect before the initial fetch lands. Full make verify passed on 2026-08-12 (914 pytest cases, 30 golden scenarios).
