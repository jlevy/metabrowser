---
type: is
id: is-01m78tvrkk9r65aq6w6jd52kxr
title: "PR #379 D1: badge reconciliation ignores batch() and reads each target twice"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:16.260Z
updated_at: 2026-11-12T22:38:58.628Z
started_at: 2026-11-12T21:33:41.558Z
closed_at: 2026-11-12T22:38:58.627Z
close_reason: "Fixed in a09ff3a5: badges reconcile once per outermost batch; each target read once a pass. Revealed navigation 112/98 -> 11/10 liveness reads, handled key 18 -> 11, at rest 0 and 1. Reply: https://github.com/jlevy/metabrowser/pull/379#issuecomment-6837880767"
resolution: null
duplicate_of: null
---
Medium. PR #379, review D (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899935). static/keyboard-shortcuts.js:733-737 followBadges() runs a full reconcileBadges() on every change while revealed, and batch() (:546-565) coalesces only publications; reconcileBadges() (:716-731) reads every live command's targets twice (entryIsLive then firstLiveTarget). Measured 113 and 99 liveness reads per revealed navigation and 18 per handled key.
