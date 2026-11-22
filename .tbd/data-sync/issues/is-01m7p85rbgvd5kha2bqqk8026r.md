---
type: is
id: is-01m7p85rbgvd5kha2bqqk8026r
title: "After everything lands: rebuild and restart the dev app from main, and confirm it runs main's head"
kind: task
status: in_progress
priority: 1
version: 6
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-18T02:36:02.799Z
updated_at: 2026-11-22T23:53:05.783Z
started_at: 2026-11-22T21:54:34.439Z
---
Local build review owns app-review-build; its last quit request was refused ('User canceled'), so the owner may need to quit and reopen.

## Notes

Rebuilt and normally relaunched the active development app at candidate 9c6e73b47. The saved window restored and its server responds from metab 0.13.0.dev2984+9c6e73b. Candidate contains #708 plus the reviewed native-open, 16-item recent menus, folder-menu and muted-indexing fixes (#712 and #713). Refresh from merged main remains pending the hosted main CI gate.
