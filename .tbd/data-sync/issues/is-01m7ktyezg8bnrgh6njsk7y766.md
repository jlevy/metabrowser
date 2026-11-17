---
type: is
id: is-01m7ktyezg8bnrgh6njsk7y766
title: "PR #496 review A5: the interpreters main runs are a copy in ci_plan.sh outside the workflow"
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:23.472Z
updated_at: 2026-11-17T04:06:23.472Z
---
plan:419-423, :194-199. check_ci.py reads ci.yml, so a list hardcoded in ci_plan.sh could drift from the classifiers.
