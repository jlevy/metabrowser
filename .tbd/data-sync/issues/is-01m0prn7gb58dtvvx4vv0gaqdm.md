---
type: is
id: is-01m0prn7gb58dtvvx4vv0gaqdm
title: "PR #72 review R7: --chip-height has one consumer, so the reservation tracks real chips only by comment"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:14.282Z
updated_at: 2026-08-23T08:07:30.939Z
closed_at: 2026-08-23T08:07:30.938Z
close_reason: "Fixed in 552a41d. --chip-padding-y and --chip-border are the single source; --chip-height derives from them and .chip reads them back, so the reservation and the real chip cannot disagree. .chip-group takes the border token too. Verified: no pixel moved (24px chip, 22 inside a 24px group, 37px bar against a 37px reservation)."
---
styles.css:379 defines it, :2735 is the only use; .chip at :2456 declares its own padding 2px 9px and border 1px, which the token re-encodes as +6px. Change .chip's padding and the bar goes short silently — the test only checks that 'var(--' appears. Fix: give .chip min-height: var(--chip-height) so the token is normative.
