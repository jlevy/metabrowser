---
type: is
id: is-01m2h9a1hy7rbcarq3xjym7rnf
title: "PR #125 review C-R7: distinguish traversal completeness from remote consistency"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:10.586Z
updated_at: 2026-09-15T01:38:10.628Z
closed_at: 2026-09-15T01:38:10.627Z
close_reason: "Fixed C-R7: added remote-consistency states, first/last observation times, stable sort/tie-break, per-page provenance, stable-ID deduplication, and bounded completeness semantics."
resolution: null
duplicate_of: null
---
PR #125 contracts C-R7. Add remote consistency state, first and last page observation times, stable sort and tie-breaker, continuation provenance, and stable-ID deduplication. Define complete only as traversal exhaustion within bounds unless the provider guarantees a snapshot.
