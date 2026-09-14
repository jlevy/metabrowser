---
type: is
id: is-01m1apk8f1vcbzayrj4kthw7bt
title: "PR #90 P90-19: Watch items from the review"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:23:01.216Z
updated_at: 2026-09-14T07:01:00.833Z
closed_at: 2026-09-14T07:01:00.832Z
close_reason: "Both items already fixed on main; recorded in PR #116. (a) /api/index/progress is in api_cli._INDEX_DEPENDENT, so --api waits for the scan and the golden pins the settled answer (bf2b0e74); held 3/3 runs. (b) api_routes reads request.app.routes and reports Mount methods as null (501b31b, CODE-08 / mb-pyi1)."
resolution: null
duplicate_of: null
---
The /api/index/progress snapshot is scheduling-dependent, and api_routes reads the module-global app and reports Mount methods loosely.
