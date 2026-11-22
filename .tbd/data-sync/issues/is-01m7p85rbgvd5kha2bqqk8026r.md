---
type: is
id: is-01m7p85rbgvd5kha2bqqk8026r
title: "After everything lands: rebuild and restart the dev app from main, and confirm it runs main's head"
kind: task
status: in_progress
priority: 1
version: 5
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-18T02:36:02.799Z
updated_at: 2026-11-22T22:17:09.405Z
started_at: 2026-11-22T21:54:34.439Z
---
Local build review owns app-review-build; its last quit request was refused ('User canceled'), so the owner may need to quit and reopen.

## Notes

Updated and normally relaunched the active development app at candidate 032d89bac after the independent link review follow-up. Both restored servers are responding from the updated metab runtime. Candidate includes the PR nav byte cleanup, SQLite notice recovery, and readable repository/branch GitHub links. Final refresh from main remains pending hosted merge checks.
