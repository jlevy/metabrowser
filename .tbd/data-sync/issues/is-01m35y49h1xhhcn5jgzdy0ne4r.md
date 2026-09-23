---
type: is
id: is-01m35y49h1xhhcn5jgzdy0ne4r
title: Verify whole-stack mergeability and publish the feature/testing walkthrough
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md
delegate: codex@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-23T01:29:50.880Z
updated_at: 2026-09-23T02:04:05.975Z
started_at: 2026-09-23T01:30:26.431Z
closed_at: 2026-09-23T02:04:05.973Z
close_reason: "Published full feature/test walkthrough on #225 ef334432; all eight PRs are ready, contiguous, mergeable/clean and green on fresh CI. No tbd gate. Local verify and pre-push passed; ongoing product acceptance remains tracked separately."
resolution: null
duplicate_of: null
---
Follow user clarification: no tbd-related release or process hold. Verify current Stack 218 ancestry, conflicts, CI and draft/review state without merging. Reconcile tbd-maintenance tracking and publish a complete built/in-progress/planned feature map plus practical testing milestones and walkthrough on PR #225.

## Notes

2026-09-22 final follow-up: PR #225 is updated to ef334432dde5449d29a7f097a8dc2084fdb08f20 over unchanged #216 b3c001a96eed64eb77961c2b7165b103af98b77c. All eight Stack 218 PRs are OPEN, non-draft, contiguous, MERGEABLE/CLEAN, with seven successful checks each. Current main 6c278f3f is an ancestor of the integration tip. Fresh CI: https://github.com/jlevy/metabrowser/actions/runs/35808364944 . Final evidence and walkthrough: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787687825 . Full review ledger: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 .

The expanded feature map distinguishes built, partial and planned scope and later work, with T0 available now, the first default-branch URL browser checkpoint after 2A, full T1 after selected-ref/branch integration, direct PR T2 and discovery/navigation/anchors T3. The explicit Phase 2B background worker is mb-bgn8; M10b covers provider rebind. Local make verify and the pre-push gate passed (3112 pytest tests, two skips; 147 CLI transcript checks; audits and installed-wheel/distribution checks). The real CLI cold/warm/origin-absent T0 smoke passed; fixture-server startup/HTTP was checked, without claiming full manual visual acceptance or GitHub URL/PR E2E support. Astra checked feature/design boundaries and Sol verified fresh CI, ancestry, mergeability and documentation consistency.

No tbd release, upgrade or shortcut cleanup is a prerequisite for product implementation, testing, landing or release. mb-dbue/#219 are independent optional maintenance. This supersedes historical notes mentioning an upstream tbd release wait. Product acceptance findings including mb-sumg remain open; mb-gnr9 owns future installed/browser acceptance. Future work extends this same stack, and whole-stack landing awaits product stabilization and explicit user approval. No merge or release was performed.
