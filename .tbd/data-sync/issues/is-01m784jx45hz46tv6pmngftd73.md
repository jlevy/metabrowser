---
type: is
id: is-01m784jx45hz46tv6pmngftd73
title: "Git route memo: one record per location, and share in-flight work between concurrent requests"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-12T15:03:57.315Z
updated_at: 2026-11-12T15:03:57.315Z
---
Deferred from review A (A5) and B (B7) on jlevy/metabrowser#368. Four server stores hang off one ref state; requests that arrive together share no in-flight work. Restructure into one record per served location and coalesce concurrent identical requests, as its own measured change (requests arriving together; memory per location). Not a regression.
