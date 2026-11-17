---
type: is
id: is-01m7kpnbgvh17pnc0z229034gd
title: "CI speed 2.1: split ci.yml into unit, goldens, and chrome jobs, with no fail-fast, cancellation of superseded pull request runs, time limits, a ci-ok verdict job that fails while main is red, and the merge procedure"
kind: task
status: open
priority: 1
version: 7
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
updated_at: 2026-11-17T04:07:45.976Z
---
Phase 2 of plan-2026-11-16-fast-ci.md: Jobs, A Red main, and Proposed Workflow. The owner answered Q1, Q3, and Q5; Q6 was decided 2026-11-17. unit runs make test-parallel on 3.12, 3.13, 3.14, and 3.14t. goldens runs make test-goldens, then make test-serial under if: !cancelled(), on the same four, so the serial tier keeps every interpreter before the merge (review A1 of #496). chrome runs make test-chrome SHARD=I/4 on the plan job's chrome-pythons output: PR_CHROME_PYTHON (3.13) for a pull request while main is green, and PYTHONS (all four) for a push to main and for a pull request to main while main is red. PYTHONS and PR_CHROME_PYTHON are env values on the plan job's step in ci.yml, not literals in ci_plan.sh (review A5). The plan job is the one job with actions: read (review A2): for a pull request to main it reads main's state, which is the conclusion of the newest ci.yml run of a push to main, or, while that run is going, of its previous attempt (a rerun) or of the run before it (a first attempt). Only success is green; any other answer, or a failed read, is red, which costs runner minutes and never coverage. ci-ok (if: always()) fails unless every needed job succeeded, and names main's red run in its verdict, so only a pull request that repairs a red main passes it. Add the merge procedure to AGENTS.md's Git section, with its reason (a ci-ok that went green before main turned red still reads green): after each merge the merging agent watches the merge commit's ci.yml run to its end; while it is red it merges only a pull request whose ci-ok ran main's whole matrix, reruns a failure that a bead names as a known flake once, and gives any other failure a bead and a fix or a revert. concurrency cancels a superseded pull request run and never a main run; timeout-minutes is about 1.5 times each job's measured 90th percentile, with the measurement beside it. Record the actions: read grant in SUPPLY-CHAIN-SECURITY.md. Accept: over 20 pull request runs after the merge, median push to green at or under 5 minutes and 90th percentile at or under 6, and unit, the serial tier, and chrome together collect the tests the test job collects on the same commit; ci_plan.sh's tests over recorded API answers (success, failure, cancelled, no run, a failed read, a first attempt in progress, a rerun in progress) widen the Chrome tier on every answer but success; the first pull request run after main is next red runs the Chrome tier on all four, and ci-ok names main's run. If a unit leg's 90th percentile is over 4.5 minutes, split each unit job with SHARD=I/2. Measure the queue wait again: the sample's running jobs held a ceiling of 40, and a main run is now 30 jobs.

## Notes

2026-11-16: the owner answered plan Q1 (approved: restructure ci.yml through reviewed pull requests), Q3 (the serial tier runs on Python 3.13 for a pull request and on all four interpreters for every push to main), and Q5 (the owner sets a ruleset requiring ci-ok on main once the job exists; that setting is the owner's step, not this bead's). Relayed by the coordinating session.

2026-11-17: owner approved the workflow changes (Q1, 2026-11-16), so the workflow-file OK in this title is given.
