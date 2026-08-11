---
type: is
id: is-01ky8hr1eszy04k93pqyd4cb28
title: "Bugbot R3-2: route handler must honor the folder marker"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-23T22:32:40.664Z
updated_at: 2026-07-23T22:45:16.061Z
closed_at: 2026-07-23T22:45:16.060Z
close_reason: "handleRouteChange compares (path, isDir) vs the last committed route; live-verified a #README.md -> #README.md/ flip re-navigates and normalizes."
---
handleRouteChange compares only parts.path, so a hash flip between #path and #path/ (file vs folder route) at the same string skips navigation. Compare (path, isDir) against the last committed route.
