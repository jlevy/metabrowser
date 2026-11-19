---
type: is
id: is-01m7tb9yx38183fpesfy0pme7a
title: "Host mode H4: metab ROOT --api ROUTE --live reaches the root's live server"
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-18-host-mode.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-19T16:47:44.034Z
updated_at: 2026-11-19T16:49:47.546Z
---
Host mode plan step H4 (docs/project/specs/active/plan-2026-11-18-host-mode.md, Implementation Plan and Discovery; Decision HM-1 A, taken 2026-11-19). New.

Delivers: metab ROOT --api ROUTE --live issues the route to the most specific registered root that holds ROOT, read from H3's registry. It starts nothing, and fails with a distinct exit status when no server is live. It uses loopback for an open server; the control socket transport for a gated server arrives with mb-1zyp. Goldens against a fixture runtime directory and a harness server.

Slot: after H3; in Ordering 2, Stack V after V5 (--api --server).
