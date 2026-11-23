---
type: is
id: is-01m7p85rbgvd5kha2bqqk8026r
title: "After everything lands: rebuild and restart the dev app from main, and confirm it runs main's head"
kind: task
status: in_progress
priority: 1
version: 8
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-18T02:36:02.799Z
updated_at: 2026-11-23T01:05:19.589Z
started_at: 2026-11-22T21:54:34.439Z
---
Local build review owns app-review-build; its last quit request was refused ('User canceled'), so the owner may need to quit and reopen.

## Notes

Rebuilt and normally relaunched the active development app from consolidated 90e03a053 at metab 0.13.0.dev3024+90e03a0. The saved window restored, its server responded, and the affected checkout’s Pulls refreshed to current automatically. Verified the same catalog on an isolated pinned read. Development bundle includes the latest menu, PR Overview and 92-percent window sizing. The ARM64 ad hoc release rehearsal checked the DMG, checksum, and cask. Refresh from the final merged main remains pending gated PRs.
