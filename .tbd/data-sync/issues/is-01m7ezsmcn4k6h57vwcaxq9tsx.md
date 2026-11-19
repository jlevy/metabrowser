---
type: is
id: is-01m7ezsmcn4k6h57vwcaxq9tsx
title: "H117: a resident server and shell — a rootless metab, imported and bound, adopts a folder on a control message"
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7exbshjz1sx7r322nye458d
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:54:55.892Z
updated_at: 2026-11-19T16:49:35.181Z
---
Architecture review R6; the core half of mb-bbod and mb-25nv. Decides open to first /api/tree rows 0.5–0.8 s → ≤ 100 ms, and in WKWebView open to painted ready with no document load. Needs host mode's control channel (mb-qzny) and H97 (mb-touu), a rootless start, and an adopt arm in startup_pairs.py. Reserved exp-097. Registry row H117.

## Notes

2026-11-19: restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md). Host mode's control channel is the owner-only control socket, mb-1zyp (H7); mb-qzny now holds only the token (H8). This bead waits on mb-1zyp in place of mb-qzny, and still on mb-touu.
