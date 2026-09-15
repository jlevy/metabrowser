---
type: is
id: is-01m2h99t9nsnt7z8e6t48rxh6v
title: "PR #125 review A-R5: separate transient projection ownership"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies: []
parent_id: is-01m2h984s9t8fhm2efg67nwmve
created_at: 2026-09-15T01:01:03.153Z
updated_at: 2026-09-15T01:38:06.091Z
closed_at: 2026-09-15T01:38:06.090Z
close_reason: "Fixed A-R5: renamed the shared lifetime category transient projections while preserving source-specific ownership for repository worktrees, archive extraction, provider anchors, and recomputable session caches."
resolution: null
duplicate_of: null
---
PR #125 architecture A-R5. Rename the shared lifetime category transient projections while keeping detached Git worktrees in the repository library, review anchors in hosted review or diff, and archive extraction in archive consumers. Share only proven low-level helpers.
