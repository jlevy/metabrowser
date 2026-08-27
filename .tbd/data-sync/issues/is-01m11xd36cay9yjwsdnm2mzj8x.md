---
type: is
id: is-01m11xd36cay9yjwsdnm2mzj8x
title: "PR #31 review R3: shared is_clean dependency recorded nowhere that enforces it"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:49.355Z
updated_at: 2026-08-27T15:44:26.720Z
closed_at: 2026-08-27T15:44:26.718Z
close_reason: "Fixed in dbe3206: Phase Dependency Map row plus prose in both plans, below-2.36 behavior defined as unavailable (never inferred clean), and mb-ew38 now depends on mb-u4mf in the bead graph."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:409-411,861-874,896. Phase Dependency Map has no Git-status row; mb-k7zy has no edge to mb-u4mf; below Git 2.36 the predicate does not exist and neither plan says what integrity does.
