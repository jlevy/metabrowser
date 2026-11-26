---
type: is
id: is-01m8bg10ty4vhe169tzegjdqkp
title: "Layer 1: PullStatus, ChecksSummary, PullChecks, and the readiness derivation, with GitHub's buckets"
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/876
    at: 2026-11-26T08:46:40.928Z
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m8bg123m2pt6a6yjt804abrb
parent_id: is-01m8be447e9931hjyw4nrg4qxe
hold: null
hold_until: null
created_at: 2026-11-26T08:37:19.326Z
updated_at: 2026-11-26T22:22:46.575Z
started_at: 2026-11-26T08:41:25.860Z
closed_at: 2026-11-26T22:22:46.575Z
close_reason: "Merged to main with stack #877 (jlevy/metabrowser#876, #879, #883, #884), merge 68c54f030."
resolution: null
duplicate_of: null
---
pull_status.py and pull_readiness.py per the spec's Status Model and Readiness sections, following GitHub's classification (rollup for the summary, gh pr checks buckets per check). Invariant tests generated over the enums.
