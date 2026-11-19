---
type: is
id: is-01m748xw1h1hx5p0eakfc0afgr
title: "Host mode H7: control verbs (identity, present, clients, close) on an owner-only socket"
kind: feature
status: open
priority: 2
version: 12
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xv63xk4wtt5nrrr64s2q
  - type: blocks
    target: is-01m7ezsmcn4k6h57vwcaxq9tsx
  - type: blocks
    target: is-01m748y1pa5yyy4wf2t16cpf0y
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:53.232Z
updated_at: 2026-11-19T16:59:18.774Z
---
Host mode plan step H7, the control socket (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and Reaching a Gated Server; Decisions HM-1 A and HM-4 A, taken 2026-11-19). After discovery (mb-baee), whose server record names the socket's path, and before the token (mb-qzny).

Delivers: HTTP over an owner-only Unix socket, its path within macOS's length limit, on an allowlist of registered routes: GET /api/identity, GET /api/ui/viewers and GET /api/ui/viewer, POST /api/ui/intents, and a new close route that stops the server. The server also refuses a peer whose user ID, read from the kernel, is not the owner's. A mark on each /api/routes entry the socket serves, and --live (mb-77x9) choosing the socket where a server is gated. Content routes stay on loopback. Goldens for each, with the view model's goldens run again over the socket against a gated harness server. The identity fields pid, boot_id, and version are mb-hhzd (H1).

## Notes

2026-11-19: restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md, step H7; HM-4 A). Previously described as "Phase 3. Extend /api/identity with pid, boot id, and version; add present (pushes a navigate event to the root's most recently visible page), clients, and close. Only these verbs are served on the owner-only Unix socket (path within 104 bytes); content routes stay on loopback behind the page token. Goldens for each." Its first clause, the identity fields, moved to mb-hhzd (H1); present and clients are now the view model's intents and viewer routes, served over the socket as HTTP on an allowlist. Dependencies: the edge with mb-qzny is reversed, so this bead now blocks mb-qzny (the socket before the token); now blocked by mb-baee, whose record names the socket; no longer blocks mb-54r1 (which needs the boot ID, mb-hhzd) or mb-idri (which needs discovery and the lock, not the socket); now blocks mb-obgj and mb-bbod, which need host mode's control channel.
