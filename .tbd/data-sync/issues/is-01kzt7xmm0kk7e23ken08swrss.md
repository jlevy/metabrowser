---
type: is
id: is-01kzt7xmm0kk7e23ken08swrss
title: "PR #32 review MB32-R2: align recency pending-tally repaint paths"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzt7x3qqb7y2qgpbxhjg3k3x
created_at: 2026-08-12T05:42:59.967Z
updated_at: 2026-08-12T05:56:10.933Z
closed_at: 2026-08-12T05:56:10.932Z
close_reason: "Fixed in c263112: completion recovery scopes to the Files panel and re-reads/repaints the active recency source after the tree refresh."
---
PR #32 senior review MB32-R2 (Low). src/metabrowser/static/app.js around refreshTreeIfPendingTallies and the watchdog. Scope pending selectors consistently and re-read the recency window after loadTree before repainting.
