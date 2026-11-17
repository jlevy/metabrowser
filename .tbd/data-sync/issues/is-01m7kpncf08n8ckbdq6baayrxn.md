---
type: is
id: is-01m7kpncf08n8ckbdq6baayrxn
title: "CI speed 2.3: run stack-integration only when merging main changes the tree, and as split jobs"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpnfbtzejh3redbeppejmp
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:31.679Z
updated_at: 2026-11-17T04:22:26.687Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, Stacks; Q4 is open, so build it as the plan proposes and ask again in the pull request. devtools/ci_plan.sh computes the merge of the pull request's head with main by git merge-tree --write-tree and compares its tree with the tree of the merge commit the other jobs check out: identical runs nothing more; different runs seven jobs on the head merged with that exact main commit, on Python 3.13: lint-check, test-parallel, '-k test-goldens test-serial' (make -k, so a golden failure still reports the serial tier, review B8), and the four test-chrome shards; a conflict fails ci-ok with today's message. Each job sets git config user.name and user.email before git merge, as today's job does, or a merge that makes a commit fails (review A3 of #496). The plan job always runs and writes the event, base, both trees, main's state, and its decisions to its summary. A stacked pull request does not read main's state: it reaches main through a run whose base is main. Measured today: the single job takes a median of 19.4 minutes, and in 33 of 69 sampled stacked runs the merge printed 'Already up to date.', an upper bound on identical trees. Accept on three pull requests: a stack behind main, one level with it, and one that conflicts.

## Notes

2026-11-16: plan Q4 (the plan job's summary as the record of a skipped integration) was not asked of the owner; build it as the plan proposes and ask again in the pull request.
