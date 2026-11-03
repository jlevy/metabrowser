---
type: is
id: is-01m6g886gmdr9vtphf25n922k6
title: "PR #287 A3: cancel delayed file walks when navigation ownership changes"
kind: bug
status: in_progress
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6g771qn4n0pce8m7sdmmhxy
hold: null
hold_until: null
created_at: 2026-11-03T08:26:14.419Z
updated_at: 2026-11-03T11:44:14.153Z
started_at: 2026-11-03T08:32:59.279Z
---
Independent strong review: pending120ms key walk can overwrite later setCurrent route selection or hidden panel. Cancel on external route/hide changes, keeping self scroll reports separate.

## Notes

Fixed locally in 18e0d8da; recheck pin be99626f. External route selection, panel/document hiding, and focused-tree changes cancel pending file walks. Diff scroll feedback uses followCurrent and preserves the active walk. Production controller golden covers route cancellation, hide cancellation, and self-scroll feedback retaining one final history replacement. Normal hooks pass; awaiting independent recheck and coordinator push.

2026-11-03 independent-review integration at final tip 58270d69. Review B independently verifies A3 fixed: external routing, hiding, and focus ownership cancel pending walks; scroll feedback preserves a legitimate active walk. Retained at owning #287 0b7b62c5. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
