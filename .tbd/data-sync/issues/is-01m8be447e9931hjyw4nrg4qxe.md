---
type: is
id: is-01m8be447e9931hjyw4nrg4qxe
title: "Merge readiness phase 1: PullStatus model, readiness derivation, GraphQL status reads, and the pull-statuses route"
kind: feature
status: in_progress
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
labels: []
dependencies:
  - type: blocks
    target: is-01m8be45aq589e23647qn19ee1
parent_id: is-01m8be438xa5kc27fpbd5rkbcy
child_order_hints:
  - is-01m8bg10ty4vhe169tzegjdqkp
  - is-01m8bg123m2pt6a6yjt804abrb
  - is-01m8bg139z95kertfgrezqqksx
  - is-01m8bg14grjg4kqt1bvhan6v5g
created_at: 2026-11-26T08:04:03.950Z
updated_at: 2026-11-26T08:41:27.747Z
---
Phase 1 of the merge readiness spec: pull_status.py and pull_readiness.py with invariant tests; the page's PullStatus GraphQL read replacing the REST check-runs and status reads; mergeable and the checks parts move out of PullRequest and PullRecord (PULL_RECORD_SCHEMA raised); the pull_status table and pulls/<n>.checks.json; the Pulls tab's PullStatuses scan; envelope status/readiness/checks, GET pull-statuses, the --show model line; goldens, parity rows, route table, map; measured costs beside constants; answer the GitHub-behavior open questions; changelog fragment.
