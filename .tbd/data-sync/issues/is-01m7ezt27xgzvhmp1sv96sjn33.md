---
type: is
id: is-01m7ezt27xgzvhmp1sv96sjn33
title: "U4: k pages on one origin — each holds one of six connections for /api/events"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-performance-campaigns.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-15T06:55:10.076Z
updated_at: 2026-11-15T06:55:10.076Z
---
Architecture review uncertainty U4 (app.js's EventSource). Read with explorations/page-connections/measure.mjs at k live tabs, then k web views, before native tabs ship; it decides whether the stream must be parked or shared.
