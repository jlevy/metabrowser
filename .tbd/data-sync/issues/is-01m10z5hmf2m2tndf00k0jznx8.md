---
type: is
id: is-01m10z5hmf2m2tndf00k0jznx8
title: Git status and dirty working-tree browsing
kind: epic
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md
labels: []
dependencies: []
child_order_hints:
  - is-01m10z5s3nhwmdyp1dcbwfwc33
  - is-01m10z5zm6bknq2q57dsfjfv31
  - is-01m132tzn4pek5ew15mreke534
  - is-01m1389tccq35y5z8ya6dpycwn
  - is-01m12w4tz60cps1t8d6z1v4zet
created_at: 2026-08-27T06:40:24.718Z
updated_at: 2026-11-20T17:17:06.555Z
---
Add a read-only Git status surface and one-file working-tree diffs through File Diff Format, following the linked phased plan.

## Notes

2026-11-14 audit: no phase started. The repository library no longer depends on is_clean (plan-2026-08-11 Phase Dependency Map), so the original ordering reason for P1 is gone; priority left for the user.

2026-11-20 audit: Git status and dirty working-tree browsing: Phases 0 to 2 and the goldens are open. mb-2wdh (the design review's delivery-order umbrella) was added.
