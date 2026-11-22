---
type: is
id: is-01m7p85rbgvd5kha2bqqk8026r
title: "After everything lands: rebuild and restart the dev app from main, and confirm it runs main's head"
kind: task
status: in_progress
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-18T02:36:02.799Z
updated_at: 2026-11-22T22:02:11.475Z
started_at: 2026-11-22T21:54:34.439Z
---
Local build review owns app-review-build; its last quit request was refused ('User canceled'), so the owner may need to quit and reopen.

## Notes

Rebuilt and restarted the active development app on candidate 2d7e28756. Verified the native process uses its updated metab runtime and a live server answers /api/routes. The final refresh against current main is pending the recovery, PR navigation, and clean GitHub destination follow-ups.
