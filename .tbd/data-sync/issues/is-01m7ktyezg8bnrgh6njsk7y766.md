---
type: is
id: is-01m7ktyezg8bnrgh6njsk7y766
title: "PR #496 review A5: the interpreters main runs are a copy in ci_plan.sh outside the workflow"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7ktycr1m7798eaqhyky3qnr
created_at: 2026-11-17T04:06:23.472Z
updated_at: 2026-11-17T04:08:32.488Z
closed_at: 2026-11-17T04:08:32.488Z
close_reason: "Fixed in 8b4da0cb: PYTHONS and PR_CHROME_PYTHON are env values on the plan job's step in ci.yml; check_ci.py (mb-to1c) holds them and the matrices to the classifiers."
resolution: null
duplicate_of: null
---
plan:419-423, :194-199. check_ci.py reads ci.yml, so a list hardcoded in ci_plan.sh could drift from the classifiers.
