---
type: is
id: is-01m2mk1k3t90h99zszfa8pq9c1
title: "Phase 0C.2 review R5: detect omitted capability providers independently"
kind: bug
status: in_progress
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:02.713Z
updated_at: 2026-09-16T07:49:10.710Z
---
The distribution gate compares installed registries only with capability providers that survived into the same wheel, so an omitted intended entry point and its contracts/profiles can pass self-consistently. Derive the expected provider set from independent project build metadata and reconcile the installed distribution against it. Add a negative fixture or artifact mutation proving a missing declared provider is named and rejected without hard-coding hosted-review IDs.
