---
type: is
id: is-01m1cdvt7verq3yp1b5hefztf3
title: "PR #90 CODE-08: /api/routes fabricated methods for Mounts and read the global app"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m1cdvq5dqpv1t2svby05zhx5
created_at: 2026-08-31T17:28:53.242Z
updated_at: 2026-08-31T17:29:11.141Z
closed_at: 2026-08-31T17:29:11.141Z
close_reason: "Fixed in 501b31b; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
It reported GET for a Mount, which serves whatever its sub-application serves, and used the module-global app rather than request.app.
