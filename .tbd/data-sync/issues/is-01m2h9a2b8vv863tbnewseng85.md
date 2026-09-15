---
type: is
id: is-01m2h9a2b8vv863tbnewseng85
title: "PR #125 review C-R8: require proof before publishing tombstones"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:11.395Z
updated_at: 2026-09-15T01:38:10.983Z
closed_at: 2026-09-15T01:38:10.982Z
close_reason: "Fixed C-R8: required explicit or corroborated tombstone proof; 404, null, permission, auth, and unavailable outcomes cannot infer deletion."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R8. Treat GitHub 404 or GraphQL null under one authorization context as unavailable or not_found_under_context, retain last known state, and require explicit or corroborated deletion evidence before a tombstone. Add ambiguous permission and deletion fixtures.
