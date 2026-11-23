---
type: is
id: is-01m7p85rbgvd5kha2bqqk8026r
title: "After everything lands: rebuild and restart the dev app from main, and confirm it runs main's head"
kind: task
status: closed
priority: 1
version: 10
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-18T02:36:02.799Z
updated_at: 2026-11-23T01:44:50.717Z
started_at: 2026-11-22T21:54:34.439Z
closed_at: 2026-11-23T01:44:50.711Z
close_reason: All requested focused PRs merged. The consolidated tree exactly equals upstream main 44c475dd5. The active Mac development app and restored localhost server were verified on that exact version.
resolution: null
duplicate_of: null
---
Local build review owns app-review-build; its last quit request was refused ('User canceled'), so the owner may need to quit and reopen.

## Notes

Rebuilt and gracefully relaunched the active development app from the exact final upstream main commit 44c475dd5 with released KPress 0.3.9 and matching metab runtime. The saved window restored and uses the responsive new server. Both repository tabs and real Pulls rows were verified. The exact ARM64 release rehearsal checked the DMG, checksum, and cask.
