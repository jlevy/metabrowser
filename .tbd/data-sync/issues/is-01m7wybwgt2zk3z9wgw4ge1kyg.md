---
type: is
id: is-01m7wybwgt2zk3z9wgw4ge1kyg
title: "Fast CI Phases 1-2: the suite on four processors, and parallel jobs with one ci-ok verdict"
kind: feature
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/499
    at: 2026-11-20T17:01:22.678Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/504
    at: 2026-11-20T17:01:22.680Z
labels:
  - linear
dependencies: []
parent_id: is-01m7wysgm9rg3fdch55nst1wrn
created_at: 2026-11-17T05:37:26.000Z
updated_at: 2026-11-20T19:13:07.898Z
closed_at: 2026-11-18T02:27:38.000Z
close_reason: "Merged as native stack #505: #499 and #504"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 2b7070f3-d64c-430e-8890-711add3c255f
    linked_at: 2026-11-20T18:02:21.095Z
---
The stack #505: #499 runs the suite on four processors (Phase 1), and #504 splits the workflow into parallel jobs with one ci-ok verdict (Phase 2). Part of mb-h8zb. Created on 2026-11-20 after the fact as the stack's one bead, so the stack maps to one Linear issue.
