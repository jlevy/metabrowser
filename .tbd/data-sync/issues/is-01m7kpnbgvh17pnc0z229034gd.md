---
type: is
id: is-01m7kpnbgvh17pnc0z229034gd
title: "CI speed 2.1: split ci.yml into unit, goldens, and serial jobs, with no fail-fast, cancellation of superseded pull request runs, time limits, and one ci-ok verdict job (needs the owner's OK for workflow files)"
kind: task
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpnc003tcx5fa2qjt9pf8e
  - type: blocks
    target: is-01m7kpncf08n8ckbdq6baayrxn
  - type: blocks
    target: is-01m7kpncy9xzk6a0rhv0vxd4db
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T02:51:30.714Z
updated_at: 2026-11-17T03:05:26.034Z
---
Phase 2 of plan-2026-11-16-fast-ci.md, Proposed Workflow; needs the owner's answers to Q1 and Q3. unit and goldens run on 3.12, 3.13, 3.14, and 3.14t; serial runs make test-serial SHARD=I/4 on 3.13 for a pull request and on all four interpreters for a push to main; concurrency cancels a superseded pull request run and never a main run; timeout-minutes is about 1.5 times each job's measured 90th percentile, with the measurement beside it; ci-ok fails unless every needed job succeeded. Accept over 20 pull request runs after the merge: median push to green at or under 5 minutes and 90th percentile at or under 6, and unit plus serial collect the same tests the test job collects on the same commit. If a unit leg's 90th percentile is over 4.5 minutes, split each unit job with SHARD=I/2. Measure the queue wait again.

## Notes

2026-11-16: the owner answered plan Q1 (approved: restructure ci.yml through reviewed pull requests), Q3 (the serial tier runs on Python 3.13 for a pull request and on all four interpreters for every push to main), and Q5 (the owner sets a ruleset requiring ci-ok on main once the job exists; that setting is the owner's step, not this bead's). Relayed by the coordinating session.
