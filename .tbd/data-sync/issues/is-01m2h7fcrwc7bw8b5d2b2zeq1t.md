---
type: is
id: is-01m2h7fcrwc7bw8b5d2b2zeq1t
title: capture --record exits non-zero for a control run that misses a hard gate
kind: task
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-15T00:29:08.757Z
updated_at: 2026-11-01T17:59:55.876Z
started_at: 2026-11-01T16:21:29.818Z
---
The release-comparison recipe in explorations/performance-loop/README.md tells you to alternate the previous release and the candidate through run.py capture --record. On a repository-shaped corpus the previous release misses the first_row_ms hard gate by construction -- that gate exists to reject exactly the .gitignore pre-walk v0.1.0-v0.9.1 shipped -- and v0.9.1 also reports inventory_delivery_attribution_missing because it predates that attribution.

capture --record retains the row and then exits 1, so a driver script written the obvious way (set -e) dies after the first control run. exp-034 lost a series to this and had to resume.

The row is kept, so nothing is wrong with the evidence; what is wrong is that the exit code cannot distinguish 'the candidate crossed a gate' from 'the control is the old build the gate describes'. Options: exit zero when the recorded run is not the candidate condition, or document the behaviour in the README recipe beside the alternation loop so the next person scripts it with the failure allowed.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run.
