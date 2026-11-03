---
type: is
id: is-01m6g886zy7pn0p851hcbk79pp
title: "PR #287 A4: keep keyboard focus when a refresh removes its row"
kind: bug
status: in_progress
priority: 2
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g771qn4n0pce8m7sdmmhxy
hold: null
hold_until: null
created_at: 2026-11-03T08:26:14.909Z
updated_at: 2026-11-03T11:44:14.678Z
started_at: 2026-11-03T08:32:59.300Z
---
Independent strong review: markAnchor happens before replacement paint, old focused row is then removed leaving BODY focus. Transfer ownership after paint to settled anchor/parent when empty.

## Notes

Fixed first in315f5f5c, but independent recheck atbe99626f found offscreen250of300 anchor removed during markAnchor old-model paint before replacement paint captures focus. Root forwardfixb3346b22 retains that removed focus until new paint, guards unrelated focus. Red beforefix;5productionfocus scenarios,4wrappertests,bothTSprojects and normalhooks pass. Strong recheck atb3346b22 clean: independent probe anchor/focusa000.py, Back350, nostalewalk, retained8. Durable ReviewB draft in metabrowser-review-evidence-01a1a051; pendingstackintegration/push/CI.

2026-11-03 independent-review integration at final tip 58270d69. Review B independently verifies the completed A4 fix at b3346b22, including the300-row offscreen anchor negative control. Actual focus returns to the settled anchor; empty replacements and unrelated controls remain correct. Retained at owning #287 0b7b62c5. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
