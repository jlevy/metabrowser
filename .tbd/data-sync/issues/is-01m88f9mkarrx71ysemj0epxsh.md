---
type: is
id: is-01m88f9mkarrx71ysemj0epxsh
title: Checkout and Set up job steps occasionally take minutes in CI
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-25T04:26:49.825Z
updated_at: 2026-11-25T04:26:49.825Z
---
Found while measuring for mb-z4i7 (PR #823) over 1500 ci.yml runs (2026-11-16 to 2026-11-25; data and scripts in that PR's worktree attic, regenerable with make ci-report). Besides Set up Node, other setup steps have long tails: Checkout went over 30 s 12 times (longest 413 s), Set up job 7 times (longest 239 s), and Set up Python peaked at 54 s. Each could cancel a job at its timeout-minutes as Set up Node did. Done when each tail's phase is named from job logs (as #823 did for setup-node), and either it is bounded so a stall fails fast by name or retried, or it is recorded as outside our control with its measured rate.
