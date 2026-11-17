---
type: is
id: is-01m7kpnbgvh17pnc0z229034gd
title: "CI speed 2.1: split ci.yml into unit, goldens, and chrome jobs, with no fail-fast, cancellation of superseded pull request runs, time limits, a ci-ok verdict job, a red main that widens a pull request's matrix, and the merge procedure"
kind: task
status: closed
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7kpnc003tcx5fa2qjt9pf8e
  - type: blocks
    target: is-01m7kpncf08n8ckbdq6baayrxn
  - type: blocks
    target: is-01m7kpncy9xzk6a0rhv0vxd4db
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
hold: null
hold_until: null
created_at: 2026-11-17T02:51:30.714Z
updated_at: 2026-11-17T07:52:06.081Z
started_at: 2026-11-17T06:43:46.184Z
closed_at: 2026-11-17T07:52:06.081Z
close_reason: "Implemented in jlevy/metabrowser#504 (branch claude/ci-split-jobs, stacked on #499 as stack #505): ci.yml split into plan, unit (two whole-file shards per interpreter), goldens and serial, chrome (plan's chrome-pythons), admitted-git, stack-integration, and ci-ok; no fail-fast, superseded PR runs cancelled and main never, measured time limits; ci_plan.sh and ci_verdict.sh with tests for every state-rule case; the merge procedure in AGENTS.md (Git); the actions: read grant in SUPPLY-CHAIN-SECURITY.md. Run 44038762653 green. After-merge acceptance (20 PR runs, red main, cancellation, deliberate failing shard) is mb-ohsk."
resolution: null
duplicate_of: null
---
Phase 2 of plan-2026-11-16-fast-ci.md: Jobs, A Red main, and Proposed Workflow. The owner answered Q1, Q3, and Q5; Q6 was decided 2026-11-17.

Jobs. unit runs make test-parallel on 3.12, 3.13, 3.14, and 3.14t. goldens runs make test-goldens, then make test-serial under if: !cancelled(), on the same four, so the serial tier keeps every interpreter before the merge (review A1 of #496). chrome runs make test-chrome SHARD=I/4 on the plan job's chrome-pythons output: PR_CHROME_PYTHON (3.13, "narrow") for a pull request while main is green, and PYTHONS (all four) for a push to main and for a pull request to main while main is red. PYTHONS and PR_CHROME_PYTHON are env values on the plan job's step in ci.yml (review A5).

Main's state (reviews A2, B2, C4). The plan job is the one job with actions: read. For a pull request to main it reads one page of ci.yml's push runs on main, newest first; the first run with a completed attempt gives the state. A run whose latest attempt has any status other than completed (in progress, queued, waiting, requested, pending) counts by the attempt before it (a rerun) or is passed over (a first attempt). Only success is green; any other conclusion, a failed read, or no completed attempt in the page is red.

Outputs (reviews B1, C3, C5). main-state, main-run (the run id), main-run-sha (that run's head, empty while main is green), and tests-red: yes when git merge-base --is-ancestor main-run-sha HEAD exits 0 on the merge commit this run tests. Exit 1 is "predates"; any other exit, such as 128, is a missing commit and also writes a ::warning::. Either way the reason for a no goes to the plan job's summary; never swallow the exit code. The plan job keeps today's checkout with fetch-depth: 0, which tests-red and git merge-tree need, with a comment saying so (mb-to1c holds it).

ci-ok (if: always()) fails only when a needed job fails, never on MAIN_STATE alone, which would deadlock (review B6). While main is red it writes one fixed-format line, main-red run=<id> head=<sha> tested=<yes|no>, to its log and as a ::notice:: annotation, which gh run view <run id> lists (review C2). While main is green there is no line. ci_verdict.sh's tests pin the format.

Trust boundary (review B3). Under pull_request the workflow, ci_plan.sh, and ci_verdict.sh come from the pull request's merge commit, so a change to any of them is reviewed as a change to the gate. The workflow never uses pull_request_target (mb-to1c checks it).

Merge procedure (reviews A2, B1, C1): add it to AGENTS.md's Git section, short and with no counts, with its reason (ci-ok cannot see a pull request whose run went green before main turned red, or a main run that has not completed; a verdict names the head that was red when its run was planned, so it is current only if that head is main's newest run's head):
- Merge into main only when the latest attempt of the newest ci.yml push run on main has completed (gh run list).
- If it is not green, merge only a pull request whose latest ci-ok passed with a verdict line that says tested=yes and names the head SHA of that main run.
- A rerun never changes the commit a run tested. To get a qualifying run, update the branch from main or push to it.
- Rerun a failure that a bead names as a known flake once; give any other failure a bead and a fix or a revert. Never arm auto-merge; merge directly.

Also: concurrency cancels a superseded pull request run and never a main run; timeout-minutes is about 1.5 times each job's measured 90th percentile, with the measurement beside it. Record the actions: read grant in SUPPLY-CHAIN-SECURITY.md.

Accept:
- Over 20 pull request runs after the merge, median push to green at or under 5 minutes and 90th percentile at or under 6, and unit, the serial tier, and chrome together collect the tests the test job collects on the same commit.
- ci_plan.sh's tests over completed answers (success, failure, cancelled, timed out, no run, a failed read): only success is narrow; every other answer widens the Chrome tier to PYTHONS.
- ci_plan.sh's tests over unfinished runs, each followed by the run behind it (review C4): a first attempt in progress, then success: green, narrow. A first attempt in progress, then failure: red, main-run-sha is the failed run's head. Two first attempts in progress, then success: green, narrow. A queued run, then success: green, narrow. A rerun in progress whose earlier attempt failed, then success: red, main-run-sha is the rerun's head. No completed attempt in the page: red.
- tests-red is yes for a merge commit containing main-run-sha; no, with "predates" in the summary, for one that predates it; no, with a missing-commit reason and a ::warning::, for a head the clone lacks.
- ci_verdict.sh's tests: the verdict line's format while main is red, in the log and as a ::notice::; no line while green.
- The first pull request run after main is next red, and a rerun of a run from before, both run the Chrome tier on all four; the first's verdict line says tested=yes with main's head, and the rerun's says tested=no.
- If a unit leg's 90th percentile is over 4.5 minutes, split each unit job with SHARD=I/2.
- Measure the queue wait again: the sample's running jobs held a ceiling of 40, and a main run is now 30 jobs.

## Notes

2026-11-16: the owner answered plan Q1 (approved: restructure ci.yml through reviewed pull requests), Q3 (the serial tier runs on Python 3.13 for a pull request and on all four interpreters for every push to main), and Q5 (the owner sets a ruleset requiring ci-ok on main once the job exists; that setting is the owner's step, not this bead's). Relayed by the coordinating session.

2026-11-17: owner approved the workflow changes (Q1, 2026-11-16), so the workflow-file OK in this title is given.

2026-11-17: Q3 was narrowed after review A of #496: only the tests that use chrome_profile (the Chrome tier) run on 3.13 alone for a pull request; the serial tier runs on all four interpreters. Q6 is decided: a red main widens a pull request's run to main's whole matrix, and the merging agent merges by main's state (A Red main); after review B the procedure waits for main's newest run and requires a run that tested main's red head.
