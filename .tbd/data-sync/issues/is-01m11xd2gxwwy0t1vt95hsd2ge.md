---
type: is
id: is-01m11xd2gxwwy0t1vt95hsd2ge
title: "PR #31 review R1: status command cannot emit the C records the plan models"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:48.666Z
updated_at: 2026-08-27T15:44:26.079Z
closed_at: 2026-08-27T15:44:26.070Z
close_reason: "Fixed in dbe3206: renames-only policy stated explicitly, C marked parser-only, copies dropped from the comparison mapping, copy-detection cost added as a third Phase 1 evidence gate."
resolution: null
duplicate_of: null
---
plan-2026-08-26-git-status-and-working-tree-diffs.md:246-256,202,335,396-397. git status has no --find-copies; --find-renames overrides status.renames, so 2 C... records are unreachable under the specified argv while the plan badges/models/routes copies. Verified on git 2.50.1.
