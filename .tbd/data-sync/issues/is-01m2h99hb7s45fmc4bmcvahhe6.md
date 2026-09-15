---
type: is
id: is-01m2h99hb7s45fmc4bmcvahhe6
title: "PR #125 review A-R3: specify cache and provider lock hierarchy"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:00:53.989Z
updated_at: 2026-09-15T01:38:05.303Z
closed_at: 2026-09-15T01:38:05.302Z
close_reason: "Fixed A-R3: defined home -> entry -> provider/resource lock hierarchy, prohibited network I/O under locks, and required entry/auth revalidation before atomic publication."
resolution: null
duplicate_of: null
---
PR #125 architecture A-R3. Define home, entry or lease, provider binding, and resource lock granularity and acquisition order; prohibit holding the home lock during network work; revalidate entry leases before publication; add refresh, purge, cancellation, and selected-ref concurrency coverage.
