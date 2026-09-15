---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "Hosted review Phase 0A.8: land and retarget the Phase 0A stack"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jj8edebds7zv8abfc917
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-15T18:59:54.489Z
---
After design PR 125 is approved, land it, fetch the resulting main, retarget the Phase 0A pull request to main, and inspect the exact origin/main...HEAD diff. Resolve stacking-only conflicts without broadening scope, rerun make verify, watch GitHub checks to a final green state, merge the Phase 0A pull request, and confirm main contains the merge before Phase 0B begins.
