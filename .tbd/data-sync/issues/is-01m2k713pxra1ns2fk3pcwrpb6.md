---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "Hosted review Phase 0A.8: land and retarget the Phase 0A stack"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jj8edebds7zv8abfc917
  - type: blocks
    target: is-01m2kb2nga7qt6kw5a07s2x7m1
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-09-15T20:10:34.888Z
---
After design PR 125 is approved, land it, fetch the resulting main, retarget the Phase 0A pull request to main, and inspect the exact origin/main...HEAD diff. Resolve stacking-only conflicts without broadening scope, rerun make verify, watch GitHub checks to a final green state, merge the Phase 0A pull request, and confirm main contains the merge before Phase 0B begins.

## Notes

Landing audit at origin/main c465a5f2, design head fde1d9b4, and Phase 0A head 0e8819c6: PRs #125 and #130 are CLEAN with all seven checks green; #130 is still draft. Neither PR has formal reviews, requested reviewers, inline comments, or unresolved threads. Existing comments are owner-authored technical review records. Explicit human approval remains required for each merge; approval of #125 alone will not be inferred as approval of #130.
