---
type: is
id: is-01m2mbre46mqzjejzwaqj2e3x5
title: "Phase 0C.1 review R3: add negative corpus coverage for browser semantic branches"
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c1
  - review
dependencies: []
parent_id: is-01m2krxbqajmpk9zhjm8berj18
created_at: 2026-09-16T05:41:42.660Z
updated_at: 2026-09-16T07:13:34.112Z
closed_at: 2026-09-16T07:13:34.112Z
close_reason: "Fixed in 614fef15793ff7cffd0c4e85a577342472fd9686, independently re-reviewed with no remaining findings, published in the PR #135 disposition map, and validated by green local and GitHub CI."
resolution: null
duplicate_of: null
---
Fable Medium: new ReviewThread, Check, CommitStatus, and lifecycle browser checks lack portable negative mutations. Add compact named cases for resolved_by on non-resolved thread, check self-parenting, suite parent, completed-before-started, and comment/status lifecycle inversion, then run both Python and exact production JavaScript against them.
