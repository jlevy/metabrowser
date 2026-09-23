---
type: is
id: is-01m2zvd6nbv1cagngcsnvs6jx6
title: "Phase 1B-a: distribution-backport policy for Git version strings"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
created_at: 2026-09-20T16:46:50.537Z
updated_at: 2026-09-23T03:55:20.364Z
closed_at: 2026-09-23T03:55:20.363Z
close_reason: "Decided 2026-09-22 by the user: refuse. Recorded under Git version gates in plan-2026-08-11-open-repo-from-git-url.md on codex/v012-foundation-stabilization 064c51dd; the Phase 1B-a checkbox is ticked. A version string cannot show which fixes a build carries. The refusal is the existing typed unsupported_git_version state naming the detected version and the floor, so no code change was needed. Revisit only if a common supported distribution ships no admitted Git."
resolution: null
duplicate_of: null
---
Phase 1B-a of docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md (heading at line 1774) still has this item unchecked: decide the distribution-backport policy recorded under the spec's Git version gates section, which governs how backported distribution Git version strings are admitted against the acquisition floor.
