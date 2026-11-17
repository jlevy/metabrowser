---
type: is
id: is-01m7kpnbgvh17pnc0z229034gd
title: "CI speed 2.1: split ci.yml into unit, goldens, and chrome jobs, with no fail-fast, cancellation of superseded pull request runs, time limits, a ci-ok verdict job, a red main that widens a pull request's matrix, and the merge procedure"
kind: task
status: open
priority: 1
version: 9
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
updated_at: 2026-11-17T04:22:12.140Z
---
Phase 2 of plan-2026-11-16-fast-ci.md: Jobs, A Red main, and Proposed Workflow. The owner answered Q1, Q3, and Q5; Q6 was decided 2026-11-17.

Jobs. unit runs make test-parallel on 3.12, 3.13, 3.14, and 3.14t. goldens runs make test-goldens, then make test-serial under if: !cancelled(), on the same four, so the serial tier keeps every interpreter before the merge (review A1 of #496). chrome runs make test-chrome SHARD=I/4 on the plan job's chrome-pythons output: PR_CHROME_PYTHON (3.13) for a pull request while main is green, and PYTHONS (all four) for a push to main and for a pull request to main while main is red. PYTHONS and PR_CHROME_PYTHON are env values on the plan job's step in ci.yml (review A5).

Main's state (reviews A2, B2). The plan job is the one job with actions: read. For a pull request to main it reads one page of ci.yml's push runs on main, newest first; the first run with a finished attempt gives the state. A run whose latest attempt is still going or queued counts by the attempt before it (a rerun) or is passed over (a first attempt). Only success is green; any other conclusion, a failed read, or no finished attempt in the page is red. It also outputs red-sha (that run's head) and tests-red: yes when git merge-base --is-ancestor finds red-sha in the merge commit this run tests.

ci-ok (if: always()) fails only when a needed job fails, never on MAIN_STATE alone, which would deadlock (review B6). While main is red its verdict names main's red run and red-sha and says whether this run tested that head.

Trust boundary (review B3). Under pull_request the workflow, ci_plan.sh, and ci_verdict.sh come from the pull request's merge commit, so a change to any of them is reviewed as a change to the gate. The workflow never uses pull_request_target (mb-to1c checks it).

Merge procedure: add it to AGENTS.md's Git section, short and with no counts, with its reason (ci-ok cannot see a pull request whose run went green before main turned red, or a main run that has not finished) (reviews A2, B1):
- After each merge, watch that commit's ci.yml run to its end, and merge into main only when the newest push run on main has finished.
- While that run is red, merge only a pull request whose latest ci-ok run was triggered after the red commit landed and ran main's whole matrix, so it tested main's current red head; its verdict says so. A rerun of an older run does not qualify.
- Rerun a failure that a bead names as a known flake once; give any other failure a bead and a fix or a revert.
- Never arm auto-merge; merge directly.

Also: concurrency cancels a superseded pull request run and never a main run; timeout-minutes is about 1.5 times each job's measured 90th percentile, with the measurement beside it. Record the actions: read grant in SUPPLY-CHAIN-SECURITY.md.

Accept:
- Over 20 pull request runs after the merge, median push to green at or under 5 minutes and 90th percentile at or under 6, and unit, the serial tier, and chrome together collect the tests the test job collects on the same commit.
- ci_plan.sh's tests over recorded API answers (success, failure, cancelled, no run, a failed read, a first attempt in progress, a rerun in progress, two runs in progress, a queued run, no finished attempt in the page) widen the Chrome tier on every answer but success.
- tests-red is yes for a merge commit containing the red head, and no for one that predates it or a head the clone lacks.
- The first pull request run after main is next red, and a rerun of a run from before, both run the Chrome tier on all four; ci-ok's verdict says the first tested the red head and the rerun did not.
- If a unit leg's 90th percentile is over 4.5 minutes, split each unit job with SHARD=I/2.
- Measure the queue wait again: the sample's running jobs held a ceiling of 40, and a main run is now 30 jobs.

## Notes

2026-11-16: the owner answered plan Q1 (approved: restructure ci.yml through reviewed pull requests), Q3 (the serial tier runs on Python 3.13 for a pull request and on all four interpreters for every push to main), and Q5 (the owner sets a ruleset requiring ci-ok on main once the job exists; that setting is the owner's step, not this bead's). Relayed by the coordinating session.

2026-11-17: owner approved the workflow changes (Q1, 2026-11-16), so the workflow-file OK in this title is given.

2026-11-17: Q3 was narrowed after review A of #496: only the tests that use chrome_profile (the Chrome tier) run on 3.13 alone for a pull request; the serial tier runs on all four interpreters. Q6 is decided: a red main widens a pull request's run to main's whole matrix, and the merging agent merges by main's state (A Red main); after review B the procedure waits for main's newest run and requires a run that tested main's red head.
