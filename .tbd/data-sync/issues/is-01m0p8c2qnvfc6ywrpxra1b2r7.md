---
type: is
id: is-01m0p8c2qnvfc6ywrpxra1b2r7
title: "Land #66 and #68, in that order, once v0.6.0 is confirmed on PyPI"
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies:
  - type: blocks
    target: is-01m0p8c31yfhs5sxy0qt6nztvw
created_at: 2026-08-23T02:49:37.257Z
updated_at: 2026-08-23T04:28:37.804Z
closed_at: 2026-08-23T04:28:37.804Z
close_reason: "#66 merged as fdd6c5f, #68 as 9084e6b, CI green on both merge commits. Note for the record: GitHub locked both as a stack — the normal merge and even a base retarget were refused, and the only path was PUT /repos/{owner}/{repo}/pulls/{n}/merge-async. #68 auto-retargeted to main once #66 landed and collapsed to the 1 commit / +14-7 it claimed, which is what this bead said to confirm rather than assume."
---
Two pull requests are ready and authorized to merge, but only AFTER v0.6.0 is confirmed published end to end -- not merely tagged. The release is the baseline the next bead compares against, so anything landing on main before it is confirmed muddies that comparison.

ORDER MATTERS, because they are stacked:

1. #66 `claude/perf-subtree-sweep` -- the performance work. +5630/-517 across 45 files.
2. #68 `claude/perf-architecture-hypotheses` -- docs, +14/-7 in one file, whose BASE IS #66's BRANCH, not main.

Merge #66 first. Then check #68's base: GitHub usually retargets a stacked PR to main once its base branch is merged and deleted, but confirm it rather than assume, because a stacked PR that keeps a deleted base can either refuse to merge or, worse, show a diff that is not what lands.

Before each merge, confirm CI is green on that PR's head commit, and after each, confirm CI is green on the resulting merge commit -- the second is what the next bead measures.

Gate: do not start until `uvx metabrowser@0.6.0 --doctor` succeeds from PyPI. That is the definition of published for this purpose; a green publish workflow is necessary and not sufficient.
