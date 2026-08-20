---
type: is
id: is-01m0ghe0spb1bhjzh865rhtqky
title: "Git graph: order history by date so every branch is visible"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-20T21:32:31.413Z
updated_at: 2026-08-20T21:32:31.413Z
---
The panel shows all refs (git log --all, log.py:_log_args) but orders them with --topo-order, which walks one lineage to exhaustion before switching. In this repo that means the tbd-sync branch's run of automated commits fills the whole first page: origin/main does not appear until row 459, nearly two pages past the 250-row default, so the graph reads as 'the tbd-sync branch' rather than the repository. --date-order keeps the invariant the layout needs (no parent shown before its children) while intermixing lines of history, which is what makes recent activity across branches legible and is what comparable graph UIs show. Trade-off: more lane switching per row. Verify against this repo's own history and the git graph behavior suite.
