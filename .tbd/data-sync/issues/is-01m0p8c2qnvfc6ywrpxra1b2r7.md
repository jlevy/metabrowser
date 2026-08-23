---
type: is
id: is-01m0p8c2qnvfc6ywrpxra1b2r7
title: "Land #66 and #68, in that order, once v0.6.0 is confirmed on PyPI"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-23T02:49:37.257Z
updated_at: 2026-08-23T02:49:37.257Z
---
Two pull requests are ready and authorized to merge, but only AFTER v0.6.0 is confirmed published end to end -- not merely tagged. The release is the baseline the next bead compares against, so anything landing on main before it is confirmed muddies that comparison.

ORDER MATTERS, because they are stacked:

1. #66 `claude/perf-subtree-sweep` -- the performance work. +5630/-517 across 45 files.
2. #68 `claude/perf-architecture-hypotheses` -- docs, +14/-7 in one file, whose BASE IS #66's BRANCH, not main.

Merge #66 first. Then check #68's base: GitHub usually retargets a stacked PR to main once its base branch is merged and deleted, but confirm it rather than assume, because a stacked PR that keeps a deleted base can either refuse to merge or, worse, show a diff that is not what lands.

Before each merge, confirm CI is green on that PR's head commit, and after each, confirm CI is green on the resulting merge commit -- the second is what the next bead measures.

Gate: do not start until `uvx metabrowser@0.6.0 --doctor` succeeds from PyPI. That is the definition of published for this purpose; a green publish workflow is necessary and not sufficient.
