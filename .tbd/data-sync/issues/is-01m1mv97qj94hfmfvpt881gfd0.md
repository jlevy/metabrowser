---
type: is
id: is-01m1mv97qj94hfmfvpt881gfd0
title: "PR #101 R3.1a: case folding is split-brained between ascii_casefold and .lower()"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:19.984Z
updated_at: 2026-09-04T02:07:12.755Z
closed_at: 2026-09-04T02:07:12.754Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
The contract pins ascii_casefold (contract.py:303-318) and #91 applied it to catalog and recent, but _filter_matches and _compute_navigation_tallies still fold with Unicode .lower() (python_inventory.py:2010-2021, 2502, 2519, 2539). No conformance vector covers folding. Same bug class the stack was opened to fix. Fix in-stack and add vectors (.TURKCE, I-dot.jpg).
