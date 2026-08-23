---
type: is
id: is-01m0prmjph9f84c13v7njawx4q
title: "PR #72 review R3: shipped_h for #tab-files measures markup the shell does not ship"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:33:52.976Z
updated_at: 2026-08-23T07:33:52.976Z
---
probe.js:139-142 uses the bare string 'Loading files…'; server.py:1261-1263 ships a .loading.mb-delayed-loading div holding a .spinner and an .sr-only span. .sr-only is clipped to 1px so the real text has no height; .loading is padding:32px around a 20px spinner (~84px) and visibility:hidden keeps it in flow. The probe measures one 21px body line box instead, so the 615px baseline overstates the hole by ~63px. Fix: use the real shipped markup, ideally sourced from server.py so the two cannot drift.
