---
type: is
id: is-01m11xd3gvh982tjtx3y1cdq75
title: "PR #31 review R4: CACHEDIR.TAG deferred past the phase that writes clones"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:49.690Z
updated_at: 2026-08-27T15:44:27.045Z
closed_at: 2026-08-27T15:44:27.045Z
close_reason: "Fixed in dbe3206: CACHEDIR.TAG moved to Phase 1A at cache-root creation; Phase 2 keeps size accounting only."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:787. Phase 1B publishes real clones; entries made before Phase 2 land in Time Machine/restic/borg backups.
