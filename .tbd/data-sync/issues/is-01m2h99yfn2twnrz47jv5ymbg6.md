---
type: is
id: is-01m2h99yfn2twnrz47jv5ymbg6
title: "PR #125 review C-R3: enforce owner-only cache storage"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:07.443Z
updated_at: 2026-09-15T01:38:08.800Z
closed_at: 2026-09-15T01:38:08.799Z
close_reason: "Fixed C-R3: required owner-only application-home permissions, symlink/ownership verification, and remote-acquisition refusal for unsafe cache roots while preserving ordinary local browsing."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R3. Require owner-only application home, repository entries, provider directories, staging, manifests, and snapshots; validate ownership, symlink, and overly permissive configured-home boundaries; define cross-platform behavior and permission tests.
