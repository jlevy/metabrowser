---
type: is
id: is-01m7kpncf08n8ckbdq6baayrxn
title: "CI speed 2.3: run stack-integration only when merging main changes the tree, and as split jobs"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpnfbtzejh3redbeppejmp
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:31.679Z
updated_at: 2026-11-17T07:52:06.797Z
started_at: 2026-11-17T07:08:53.533Z
closed_at: 2026-11-17T07:52:06.796Z
close_reason: "Implemented in jlevy/metabrowser#504: ci_plan.sh compares git merge-tree of head and main with the tested merge commit's tree (identical, needed, conflict), with tests on real repositories for all three; stack-integration runs as eight split jobs on the exact main commit only when needed (run 44037230262: needed, 7 of 8 green, the eighth the shard-order failure since fixed); a conflict fails ci-ok with today's message. Finding: once a PR is in a formal GitHub stack, its merge ref already merges main (run 44038762653 tested 'Merge 6dfc1ae5 into 20686e6c' = 'Merge de96415a into e442ed10'), so the plan reports identical. Q4 asked again in the PR. Conflict and level-with-main cases in CI are in mb-ohsk."
resolution: null
duplicate_of: null
---
Phase 2 of plan-2026-11-16-fast-ci.md, Stacks; Q4 is open, so build it as the plan proposes and ask again in the pull request. devtools/ci_plan.sh computes the merge of the pull request's head with main by git merge-tree --write-tree and compares its tree with the tree of the merge commit the other jobs check out: identical runs nothing more; different runs seven jobs on the head merged with that exact main commit, on Python 3.13: lint-check, test-parallel, '-k test-goldens test-serial' (make -k, so a golden failure still reports the serial tier, review B8), and the four test-chrome shards; a conflict fails ci-ok with today's message. Each job sets git config user.name and user.email before git merge, as today's job does, or a merge that makes a commit fails (review A3 of #496). The plan job always runs and writes the event, base, both trees, main's state, and its decisions to its summary. A stacked pull request does not read main's state: it reaches main through a run whose base is main. Measured today: the single job takes a median of 19.4 minutes, and in 33 of 69 sampled stacked runs the merge printed 'Already up to date.', an upper bound on identical trees. Accept on three pull requests: a stack behind main, one level with it, and one that conflicts.

## Notes

2026-11-16: plan Q4 (the plan job's summary as the record of a skipped integration) was not asked of the owner; build it as the plan proposes and ask again in the pull request.
