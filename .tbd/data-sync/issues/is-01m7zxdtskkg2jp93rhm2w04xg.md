---
type: is
id: is-01m7zxdtskkg2jp93rhm2w04xg
title: Keep cached directory timestamps current after inventory refresh
kind: bug
status: closed
priority: 2
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/686
    at: 2026-11-21T20:49:43.386Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:40:37.425Z
updated_at: 2026-11-21T20:54:38.541Z
started_at: 2026-11-21T20:42:50.323Z
closed_at: 2026-11-21T20:54:38.540Z
close_reason: Merged as jlevy/metabrowser#686 after independent review, red-green regression, and exact hosted CI.
resolution: null
duplicate_of: null
---
The existing Python inventory provider updates newest_mtime_ns after reconciliation but leaves the cached directory mtime_ns at its previous value. Reproduce add/removal and repair on main independently of the draft FDU stack. Evidence: #508 adds a strict xfail; use a passing regression against the current provider.
