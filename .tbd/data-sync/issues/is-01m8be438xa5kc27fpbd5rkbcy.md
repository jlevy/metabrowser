---
type: is
id: is-01m8be438xa5kc27fpbd5rkbcy
title: "Merge readiness: show whether a pull request is ready to merge as plainly as its state, with operational status modeled apart from the core"
kind: epic
status: in_progress
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/875
    at: 2026-11-26T08:46:39.012Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/876
    at: 2026-11-26T08:46:39.952Z
labels:
  - linear
  - Feature
dependencies: []
child_order_hints:
  - is-01m8be447e9931hjyw4nrg4qxe
  - is-01m8be45aq589e23647qn19ee1
created_at: 2026-11-26T08:04:02.970Z
updated_at: 2026-11-26T08:46:43.440Z
extensions:
  linear:
    id: cdbe63d3-7e97-4a12-b62d-a72c900972ef
    linked_at: 2026-11-26T08:21:01.651Z
---
Owner asked 2026-11-26. Every open pull request gets one readiness verdict (Ready to merge, Conflicts, Checks failing, Changes requested, Checks running, Review required, Out of date, Blocked, Queued, Checking) in GitHub's colors: on the pull request page's header and a Merge status section opening the Checks tab, and as a glyph column in the Pulls tab and on stack member rows. GitHub's mergeStateStatus decides; mergeable, the checks rollup, reviewDecision, and the merge queue explain. Operational status (PullStatus, PullChecks) becomes a model and store of its own, stamped with its head, separate from the core PullRecord. The spec opens with GitHub's model and Metabrowser's current one.
