---
type: is
id: is-01m7kpncf08n8ckbdq6baayrxn
title: "CI speed 2.3: run stack-integration only when merging main changes the tree, and as split jobs"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpnfbtzejh3redbeppejmp
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:31.679Z
updated_at: 2026-11-17T02:51:55.447Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, Stacks; needs the owner's answer to Q4. devtools/ci_plan.sh computes the merge of the pull request's head with main by git merge-tree --write-tree and compares its tree with the tree of the merge commit the other jobs check out: identical runs nothing more, different runs lint-check, test-parallel, test-goldens, and the four serial shards on the head merged with that exact main commit, and a conflict fails ci-ok with today's message. The plan job always runs and writes the event, base, both trees, and the decision to its summary. Measured today: the single job takes a median of 19.4 minutes, and in 33 of 69 sampled stacked runs the merge printed 'Already up to date.', an upper bound on identical trees. Accept on three pull requests: a stack behind main, one level with it, and one that conflicts.
