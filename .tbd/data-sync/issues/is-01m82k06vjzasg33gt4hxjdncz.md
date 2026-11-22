---
type: is
id: is-01m82k06vjzasg33gt4hxjdncz
title: Keep all same-page ref switches exclusive through navigation
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-22T21:36:08.560Z
updated_at: 2026-11-22T21:36:08.560Z
---
Follow-up to the exact-head review of PR #692. The shared POST guard ends when fetch resolves with headers. PR/diff Browse and source freshness use separate admission paths, so another same-page action can reach the server while an earlier action consumes its JSON response or hands off navigation. A focused Node probe reproduced both POSTs with a deferred first response body. Verify a mixed real menu/Browse case and share admission through response and navigation without changing cross-tab semantics.
