---
type: is
id: is-01m11xd4kkctmckz3bybzyrdcm
title: "PR #31 review R7: status cost never amortizes; corpus misses the case"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:50.802Z
updated_at: 2026-08-27T15:44:28.031Z
closed_at: 2026-08-27T15:44:28.030Z
close_reason: "Fixed in dbe3206: added the stat-dirty content-identical corpus case with the GIT_OPTIONAL_LOCKS=0 rationale and the instruction to pick debounce/timeout from it."
resolution: null
duplicate_of: null
---
plan-2026-08-26-git-status-and-working-tree-diffs.md:475-490. GIT_OPTIONAL_LOCKS=0 means the refreshed index is never written back, so stat-dirty files re-hash on every acquisition; corpus lacks a post-checkout/post-build population.
