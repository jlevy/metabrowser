---
type: is
id: is-01m1apk8f1vcbzayrj4kthw7bt
title: "PR #90 P90-19: Watch items from the review"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:23:01.216Z
updated_at: 2026-08-31T01:23:01.216Z
---
The /api/index/progress snapshot is scheduling-dependent, and api_routes reads the module-global app and reports Mount methods loosely.
