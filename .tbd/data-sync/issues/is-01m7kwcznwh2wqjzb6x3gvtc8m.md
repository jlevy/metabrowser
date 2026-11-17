---
type: is
id: is-01m7kwcznwh2wqjzb6x3gvtc8m
title: "PR #496 review C2: the plan does not say where ci-ok writes the verdict"
kind: bug
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kwcymkyzy307gn8bvwhx18
created_at: 2026-11-17T04:31:47.900Z
updated_at: 2026-11-17T04:32:09.168Z
closed_at: 2026-11-17T04:32:09.167Z
close_reason: "Fixed in 66170948: ci-ok writes main-red run=<id> head=<sha> tested=<yes|no> to its log and as a ::notice:: that gh run view lists, only while main is red; ci_verdict.sh's tests pin it."
resolution: null
duplicate_of: null
---
plan:583-584, :694. One fixed-format log line plus a ::notice:: annotation, pinned by ci_verdict.sh's tests.
