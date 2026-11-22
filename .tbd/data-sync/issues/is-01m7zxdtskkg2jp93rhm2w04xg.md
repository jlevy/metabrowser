---
type: is
id: is-01m7zxdtskkg2jp93rhm2w04xg
title: Keep cached directory timestamps current after inventory refresh
kind: bug
status: in_progress
priority: 2
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:40:37.425Z
updated_at: 2026-11-21T20:42:50.323Z
started_at: 2026-11-21T20:42:50.323Z
---
The existing Python inventory provider updates newest_mtime_ns after reconciliation but leaves the cached directory mtime_ns at its previous value. Reproduce add/removal and repair on main independently of the draft FDU stack. Evidence: #508 adds a strict xfail; use a passing regression against the current provider.
