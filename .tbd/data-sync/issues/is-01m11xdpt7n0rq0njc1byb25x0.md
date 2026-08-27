---
type: is
id: is-01m11xdpt7n0rq0njc1byb25x0
title: "PR #31 review R14: staging/ and quarantine have no reclamation rule"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:29:09.446Z
updated_at: 2026-08-27T15:44:30.253Z
closed_at: 2026-08-27T15:44:30.253Z
close_reason: "Fixed in dbe3206: added a reclamation table for staging/trash/quarantine, a Phase 1A startup sweep, and quarantine visibility from Phase 1B."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:169-170,150,245,893. Interrupted clones leave staging trees; quarantine retains indefinitely with no window and no listing until Phase 2.
