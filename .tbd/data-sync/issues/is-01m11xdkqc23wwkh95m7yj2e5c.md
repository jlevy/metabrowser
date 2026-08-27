---
type: is
id: is-01m11xdkqc23wwkh95m7yj2e5c
title: "PR #31 review R8: application-home location frozen by f01 with no rationale"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:06.276Z
updated_at: 2026-08-27T15:44:28.364Z
closed_at: 2026-08-27T15:44:28.363Z
close_reason: "Fixed in dbe3206: added 'Why one ~/.metabrowser/ rather than XDG directories' with the three reasons and the CACHEDIR.TAG mitigation."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:163-176. Neither plan nor research mentions XDG_CACHE_HOME or ~/Library/Caches; f01 names directory semantics so this becomes a migration later.
