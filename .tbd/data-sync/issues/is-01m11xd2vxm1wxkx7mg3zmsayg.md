---
type: is
id: is-01m11xd2vxm1wxkx7mg3zmsayg
title: "PR #31 review R2: Phase 1B Git version gates unspecified"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels: []
dependencies: []
parent_id: is-01m11xcje1qtw2aejrs5twn2vj
created_at: 2026-08-27T15:28:49.020Z
updated_at: 2026-08-27T15:44:26.401Z
closed_at: 2026-08-27T15:44:26.400Z
close_reason: "Fixed in dbe3206: added a Git version gates table (2.26 acquisition/blobless, 2.49 git backfill, 2.36 is_clean), full-clone fallback before publication, degrade-not-refuse detection, and a numbered patched-Git floor."
resolution: null
duplicate_of: null
---
plan-2026-08-11-open-repo-from-git-url.md:722,767. 'patched-Git floor' has no number or typed refusal state; research 2.26 floor, 2.49 git backfill gate, and full-clone fallback were dropped from the plan.
