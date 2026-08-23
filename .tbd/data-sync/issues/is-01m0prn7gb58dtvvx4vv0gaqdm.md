---
type: is
id: is-01m0prn7gb58dtvvx4vv0gaqdm
title: "PR #72 review R7: --chip-height has one consumer, so the reservation tracks real chips only by comment"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:14.282Z
updated_at: 2026-08-23T07:34:14.282Z
---
styles.css:379 defines it, :2735 is the only use; .chip at :2456 declares its own padding 2px 9px and border 1px, which the token re-encodes as +6px. Change .chip's padding and the bar goes short silently — the test only checks that 'var(--' appears. Fix: give .chip min-height: var(--chip-height) so the token is normative.
