---
type: is
id: is-01m7pqq2tsh0qgb3a3r0h04qfe
title: Untrusted documents through /api/kpress/export render in a server thread with no deadline (#527 E5)
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wyspfffhwcfcze4mke8jjp
created_at: 2026-11-18T07:07:39.224Z
updated_at: 2026-11-20T17:16:30.510Z
---
Base code, from PR #527 follow-up review E5: /api/kpress/export checks the source kind, not the mutations switch, so an untrusted folder's document renders in the server's thread with no deadline (probe: 200 with active_content=False, mutations=False). No page calls it; reach is metab --api --data or a local client. Route it through the inert child or refuse it for untrusted sources.
