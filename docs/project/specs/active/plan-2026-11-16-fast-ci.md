# Plan for Fast CI

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved for Phases 1 and 2. The owner answered Q1, Q2, Q3, and Q5 on
2026-11-16 ([Decisions and Open Questions](#decisions-and-open-questions)); Q4, Q6, Q7,
and Q8 are open.
Bead `mb-h8zb` tracks this plan, and each implementation step below is a
bead under it. Nothing here is implemented: no workflow, Makefile target, dependency, or
repository setting has changed.
The first step of each phase replaces that phase’s estimates with measurements; an
estimate is marked “est.”

## Overview

The owner asked, on 2026-11-16:

> “I need you to delegate to another sub-agent to investigate why CI is taking so long.
> This is unacceptably slow for CI. CI should be something like 3 to 5 minutes, or else
> we should figure out ways to avoid extraneous checks except when they’re appropriate.
> Delegate to a Fable sub-agent to properly assess this end-to-end and what the proper
> engineering solution is to maintain the same levels of coverage but speed up our
> development velocity.”

[Why CI Takes Twenty Minutes](../../research/research-2026-11-16-ci-speed.md) measured
the last 300 runs. A pull request waits a median of 20.5 minutes for green, because each
of four or five jobs runs the whole suite in one process on a four-processor runner.
This plan keeps every check and changes how the checks are scheduled:

- run the suite on all four processors;
- split it into unit, golden, and browser jobs that run side by side;
- run each thing as many times as it informs, and stop a flake from costing a rerun of
  everything.

The estimated result is a pull request wall clock of 4 to 5 minutes at the median, and
about 3 if the unit job is also split in two, on 36 to 41 runner minutes where a push
uses 84 today.

## Goals

- A pull request to `main` reaches a green or red verdict in 5 minutes or less at the
  median and 6 at the 90th percentile, measured as the research brief measured 20.5 and
  24.4.
- Every check that runs today runs on every commit that reaches `main`, and before the
  merge for all but one, which [How Coverage Is Kept](#how-coverage-is-kept) argues.
- A flake costs the rerun of one job of a few minutes and leaves the evidence that it
  was a flake.
- CI time has a limit that a growing suite meets as a failure with a stated remedy.
- The local `make test` and the pre-push hook get the same speedup.

## Non-Goals

- Changing what any test asserts, or deleting, weakening, or quarantining a test.
- Retrying a failed test automatically.
  The dominant flake of the sample was a product defect (`mb-alff`).
- A merge queue, larger runners, or reverting `main` automatically.
- The outer test tiers that no CI job runs today
  ([Test Tiers](../../../e2e-testing.md#test-tiers)), and `macos-app.yml`, whose median
  is 5.0 minutes.
- The start time of `metab` itself, which sets the goldens’ cost per command.

## Background

From the research brief, for the 64 hours ending 2026-11-17 01:14 UTC:

| Measure | Value |
| --- | --- |
| Pull request to `main`, push to green | median 20.5 minutes, 90th percentile 24.4 |
| Runner minutes for one push | median 84; 107 for a stacked pull request |
| A `test` leg | setup 20 seconds, pytest 14 to 16 minutes, goldens 3.3 to 4.3 minutes |
| Processors a `test` leg uses | about 1 of the runner’s 4 |
| Headless Chrome tier, per leg | 6.3 minutes on every interpreter; 20 modules, the first written 2026-11-12 |
| Times one push runs the Chrome tier | 4, or 5 for a stacked pull request |
| Run attempts that failed on a proven flake | 30 of 322; 30 of the 31 failed jobs were in the Chrome tier |
| A run that needed a rerun, push to green | median 102 minutes |
| Pull request runs superseded before they finished | 44 of 259 |
| Stacked runs whose merge with `main` was a no-op | 33 of 69 sampled |
| Green run on `main`, by week | 3.1 minutes on 2026-09-14, 22.4 on 2026-11-16 |

## Design

### Approach

Three changes carry the result, and each is independent of the others:

1. **Use the processors.** The modules that do not need a machine to themselves run
   under pytest-xdist, one worker per processor.
   The goldens run several files at a time.
2. **Split by tier.** The suite becomes three tiers that are separate jobs: a **parallel
   tier** (unit and route tests), a **serial tier** (headless Chrome and the
   process-group timing tests), and the **goldens**. The serial tier is split across
   runners, since it cannot share one.
   The wall clock is then the slowest job, not their sum.
3. **Run each thing as often as it informs.** The serial tier runs on one interpreter
   for a pull request and on all four for every commit on `main`. `stack-integration`
   runs when merging `main` changes the tree.
   A superseded run is cancelled, and a failed leg no longer cancels its siblings.

### Tiers Within `make test`

`make test` stays the definition of the default tier and still runs everything.
It becomes three targets that CI can also run one at a time:

| Target | Runs | How |
| --- | --- | --- |
| `make test-parallel` | every test not marked `serial` | `pytest -m "not serial" -n auto --dist loadfile` |
| `make test-serial` | every test marked `serial` | `pytest -m serial`, one test at a time |
| `make test-goldens` | `tests/golden/*.tryscript.md` | `devtools/run_goldens.py`, four files at a time |

- **The `serial` marker** means the test measures paint or wall-clock time and needs the
  machine to itself. `tests/conftest.py` gives it to every test that uses the
  `chrome_profile` fixture, so the Chrome tier needs no list.
  A module adds it by hand with the measurement that forced it, as a module raises its
  timeout today; `tests/test_process_group.py` is the first.
- **The two pytest targets partition the suite** by that one marker, so no test can be
  in neither. `tests/suite_gates.py` fails a test that asks for Chrome through
  `require_chrome` and is not `serial`, as it fails a module that asks for the Git floor
  from outside `ADMITTED_GIT_TESTS`.
- **`--dist loadfile`** keeps a module’s tests on one worker and in order, so
  module-scoped fixtures behave as they do today.
  The longest module is 56 seconds, so it does not limit the balance.
- **`--shard=I/N`**, a new option in `tests/`, keeps the collected tests whose index, in
  node-ID order, is `I` modulo `N`. The parts are disjoint and their union is the tier
  by construction, and a unit test holds that for the option itself.
  It needs no record of durations and no dependency.
- **`devtools/run_goldens.py`** runs one `tryscript run <file>` per golden from a queue
  of four workers, prints each file’s output whole, records each file’s time, and fails
  unless every file of the glob reported a verdict.
  The commands and the environment are the ones the `TRYSCRIPT` variable sets today.

`make test-admitted-git` runs its modules under xdist as well.
None of them is `serial` today, and a gate fails one that becomes so.

### Jobs

For a pull request to `main`:

| Job | Count | What it runs | Minutes each |
| --- | ---: | --- | --- |
| `plan` | 1 | decides the serial tier’s interpreters and whether `stack-integration` is needed | 0.2 (est.) |
| `lint` | 1 | `make lint-check audit` | 1.5 (measured) |
| `distribution` | 1 | `make build` | 0.7 (measured) |
| `unit` | 4 | `make test-parallel` on 3.12, 3.13, 3.14, and 3.14t | 3.3 to 4.0 on 3.13; 4.0 to 5.0 on 3.14t (est.) |
| `goldens` | 4 | `make test-goldens` on the same four | 1.4 to 1.8 (est.) |
| `serial` | 4 | `make test-serial SHARD=I/4` on 3.13 | 2.0 to 2.5 (est.) |
| `admitted-git` | 2 | `make test-admitted-git` on Git 2.43.7 and 2.50.1 | 2.5 to 3.0 (est.) |
| `ci-ok` | 1 | fails unless every job above succeeded | 0.1 (est.) |

That is 18 jobs and 36 to 41 runner minutes (est.), against 9 jobs and 84 today.
The wall clock is the `unit (3.14t)` job’s 4 to 5 minutes (est.). Splitting each `unit`
job in two with `SHARD=I/2` brings it to about 3 minutes; the phase’s measurement
decides, by the rule in [Time Limits](#time-limits).

The estimates divide the measured serial seconds by an assumed 2.5 to 3.2 for four
workers and add 0.4 to 0.6 minutes of setup and worker start.
That factor is the plan’s main unmeasured number; Phase 1 measures it first.

A push to `main` runs the same jobs with `serial` on all four interpreters, 16 jobs in
place of 4, and never cancels.

### How Coverage Is Kept

| Check today | On a pull request | On every commit on `main` | Why nothing is lost |
| --- | --- | --- | --- |
| `make lint-check audit` | `lint`, unchanged | unchanged | Same commands |
| `make build` | `distribution`, unchanged | unchanged | Same commands |
| pytest, tests outside the serial tier, on four interpreters | `unit` on four interpreters | same | Same tests and interpreters. With `serial`, a partition of the suite by one marker |
| pytest, serial tier, on 3.13 | `serial`, four shards | same | Shards partition the tier by construction |
| pytest, serial tier, on 3.12, 3.14, and 3.14t | not run | `serial` on all four | See below |
| tryscript goldens on four interpreters | `goldens` on four interpreters | same | Same commands; the runner fails if a file reports no verdict |
| `make test-admitted-git` on two Gits | `admitted-git`, under xdist | same | Same modules, same unpatched floor |
| `stack-integration` | The same targets on the head merged with `main`, when that tree differs from the one the other jobs ran | not applicable | An identical tree is identical input to every check |
| Strict skips | Set for every tier target | same | `STRICT_SKIPS` is on each recipe |
| `macos-app.yml` | unchanged | unchanged | Not touched |

**The serial tier on three more interpreters** is the one check that moves from before
the merge to after it.
The tier measures layout, paint, and input in Chrome against a server process.
What that server sends on each interpreter is pinned by the route tests and the goldens,
which keep running on all four before the merge, and the tier’s time is the same 6.3
minutes on every interpreter, as a browser-bound tier’s would be.
A regression that only it could catch needs a server difference between interpreters
that no route test or golden pins and that changes what the browser draws.
That is possible, most plausibly on the free-threaded build, so the check is kept: every
commit on `main` runs the tier on all four, which names the commit that broke it within
minutes of the merge.
Running it once a push also cuts the chance of a flake failing a healthy run from four
or five draws to one.
The owner chose this on 2026-11-16 (Q3); the alternative keeps all four on pull requests
for 12 more jobs and about 24 more runner minutes a push.

**`devtools/check_ci.py`**, added to `make lint-check`, keeps the table true.
It fails unless the workflow runs each of the three tier targets, the shard numbers of
each sharded job are `1` through `N`, the interpreters match the classifiers in
`pyproject.toml` and the free-threaded build, and `main` runs the serial tier on all of
them. `devtools/check_supply_chain.py` already holds the `admitted-git` matrix to both
Git floors.

### Stacks

`stack-integration` asks whether the pull request’s head still works once `main` is
merged in. The `plan` job computes that merge with `git merge-tree --write-tree` and
compares its tree with the tree of the merge commit the other jobs check out:

- **Identical:** the other jobs already answer it.
  Nothing more runs, and the `plan` job’s summary names the tree.
- **Different:** seven jobs run on the head merged with that exact `main` commit:
  `make lint-check`, `make test-parallel`, `make test-goldens`, and the four serial
  shards, on Python 3.13 as today.
  Each is 1.5 to 4 minutes (est.), where the single job takes 19.4 today.
- **Conflict:** `ci-ok` fails with today’s message, and the other jobs still run.

Today the job gates its steps, not itself, so that it always reports what it decided.
Here the `plan` job is that report: it always runs, and it writes the event, the base,
both trees, and its decision to the job summary.
Gating seven jobs by their steps would start seven runners to say that nothing was
needed. Q4, which is open, asks the owner to accept the change of convention.

Cancelling superseded runs helps stacks most, since a restack pushes every layer at
once.

### Flakes

- **No sibling is cancelled.** With `fail-fast: false`, “Re-run failed jobs” reruns the
  one job that failed, and the legs that passed stay as evidence.
  In the sample, 22 reruns re-executed 70 jobs for 22 single failing tests.
- **One draw a push.** The serial tier runs once for a pull request.
- **A machine to itself.** The serial tier never runs beside xdist workers.
- **Root fixes.** `mb-alff` and `mb-nvo0` are fixed.
  `mb-551m` and `mb-zv5s` are open, and Phase 3 adds a bead for each flake the sample
  proved that has none.
- **A nightly soak.** A scheduled workflow runs the serial tier five times on `main` and
  fails on any failure, so a flake is found away from a pull request.

### Time Limits

Each job gets a `timeout-minutes` set at about 1.5 times its measured 90th percentile,
with the measurement in a comment beside it, as
[Agent Instructions](../../../../AGENTS.md#browser-and-plugin-boundary) asks of any
limit. Run-to-run variation for one commit was about 20 percent in the sample, so the
limit does not trip on a slow runner.
It trips when a tier has grown by half, and the remedy is in the comment: add a shard,
or make the slow test cheaper.

`make ci-report` prints each job’s median and 90th percentile over recent runs from
`gh`, which makes the research brief’s tables a command.
The nightly workflow runs it and fails when a job’s 90th percentile passes 80 percent of
its limit, which is the early warning.

The `unit` jobs start unsharded.
If any `unit` leg’s 90th percentile in Phase 2’s verification is over 4.5 minutes, each
is split in two with `SHARD=I/2`.

### Path Classes

Phase 3, and only if the owner wants it (Q7). The `plan` job classes a pull request as
**light** when every changed path is under `docs/`, `apps/macos/`, or `.tbd/`, or is a
Markdown file at the repository root.
A light pull request runs `lint`, `distribution`, and `unit` and `goldens` on Python
3.13. No serial-tier or `admitted-git` module reads those paths, and the unit job runs
every test that does.
Of the last 150 merged pull requests, 24 were light.
`main` never uses classes, so a wrong rule is caught at the merge.

### Proposed Makefile Changes

The shape of the change, to be finalized by the measuring step:

```make
# Workers for the parallel tier: `auto` is one per processor. A loaded machine can
# lower it, as in `make test PYTEST_WORKERS=2`.
PYTEST_WORKERS ?= auto
# How many golden files run at a time.
GOLDEN_JOBS ?= 4
# `SHARD=I/N` runs the Ith of N parts of a pytest tier; empty runs the whole tier.
SHARD ?=
PYTEST := $(STRICT_SKIPS) $(UV_RUN) pytest -rs --durations=25 $(if $(SHARD),--shard=$(SHARD))

# The default tier, as three parts that CI also runs as separate jobs.
test: test-parallel test-serial test-goldens

test-parallel:
	$(PYTEST) -m "not serial" -n $(PYTEST_WORKERS) --dist loadfile

test-serial:
	$(PYTEST) -m serial

test-goldens:
	$(UV_RUN) python -m devtools.run_goldens --jobs $(GOLDEN_JOBS)

test-admitted-git:
	$(STRICT_SKIPS) $(UV_RUN) pytest -rs -n $(PYTEST_WORKERS) --dist loadfile $(ADMITTED_GIT_TESTS)
```

`make verify` and the pre-push hook call `make test` and need no change.

### Proposed Workflow

The shape of `ci.yml` after Phase 2. Each job’s first four steps are the ones every job
has today (checkout with full history, uv, Node, and Python), with the same pinned
actions, and are written here as `setup`:

```yaml
on:
  push:
    branches: ["main"]
  pull_request:

permissions:
  contents: read

# A newer push to a pull request supersedes its running jobs. A push to main is a group
# of its own, so every commit on main keeps its verdict.
concurrency:
  group: ci-${{ github.event.pull_request.number || github.sha }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 3
    outputs:
      serial-pythons: ${{ steps.decide.outputs.serial-pythons }}
      integration: ${{ steps.decide.outputs.integration }}
      main-sha: ${{ steps.decide.outputs.main-sha }}
    steps:
      - setup: checkout only
      - id: decide
        env:
          EVENT: ${{ github.event_name }}
          BASE: ${{ github.event.pull_request.base.ref }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
        run: bash devtools/ci_plan.sh

  lint: # as today
  distribution: # as today

  unit:
    name: unit (${{ matrix.python-version }})
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14", "3.14t"]
    runs-on: ubuntu-latest
    timeout-minutes: 8 # 1.5 times the measured p90; add a shard when it trips
    steps:
      - setup
      - run: make test-parallel

  goldens:
    name: goldens (${{ matrix.python-version }})
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14", "3.14t"]
    runs-on: ubuntu-latest
    timeout-minutes: 4
    steps:
      - setup
      - run: make test-goldens

  serial:
    needs: plan
    name: serial (${{ matrix.python-version }}, ${{ matrix.shard }}/4)
    strategy:
      fail-fast: false
      matrix:
        # ["3.13"] for a pull request; all four for a push to main.
        python-version: ${{ fromJSON(needs.plan.outputs.serial-pythons) }}
        shard: [1, 2, 3, 4]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - setup
      - run: make test-serial SHARD=${{ matrix.shard }}/4

  admitted-git: # as today; its recipe now runs under xdist

  stack-integration:
    needs: plan
    if: needs.plan.outputs.integration == 'needed'
    name: stack-integration (${{ matrix.part }})
    strategy:
      fail-fast: false
      matrix:
        part:
          - lint-check
          - test-parallel
          - test-goldens
          - test-serial SHARD=1/4
          - test-serial SHARD=2/4
          - test-serial SHARD=3/4
          - test-serial SHARD=4/4
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - setup: checkout the pull request's head, Python 3.13
      - run: git merge --no-edit ${{ needs.plan.outputs.main-sha }}
      - run: make ${{ matrix.part }}

  ci-ok:
    if: always()
    needs: [plan, lint, distribution, unit, goldens, serial, admitted-git, stack-integration]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - setup: checkout only
      - env:
          RESULTS: ${{ toJSON(needs) }}
          INTEGRATION: ${{ needs.plan.outputs.integration }}
        run: bash devtools/ci_verdict.sh
```

`devtools/ci_plan.sh` holds the decision, so that it has tests:

```bash
if [ "$EVENT" = pull_request ]; then
  serial='["3.13"]'
else
  serial='["3.12","3.13","3.14","3.14t"]'
fi
integration=none
if [ "$EVENT" = pull_request ] && [ "$BASE" != main ]; then
  git fetch --no-tags origin main
  main_sha=$(git rev-parse FETCH_HEAD)
  tested_tree=$(git rev-parse "HEAD^{tree}") # the merge commit the other jobs check out
  if merged_tree=$(git merge-tree --write-tree "$HEAD_SHA" "$main_sha"); then
    [ "$merged_tree" = "$tested_tree" ] && integration=identical || integration=needed
  else
    integration=conflict
  fi
fi
```

`devtools/ci_verdict.sh` fails unless every needed job’s result is `success`. It accepts
`skipped` only for `stack-integration`, and only when `integration` is `none` or
`identical`; `conflict` fails with today’s message.

No new action is used.
The scheduled workflow of Phase 2 uses the same pinned actions.

### Components

- `Makefile`: the tier targets and their variables
- `pyproject.toml` and `uv.lock`: `pytest-xdist` in the `dev` group, with `execnet`
- `SUPPLY-CHAIN-SECURITY.md`: the review of those two
- `tests/conftest.py`: the `serial` marker, the `--shard` option, and the `gh` guard’s
  summary reading every worker’s log
- `tests/suite_gates.py`: the gates for `require_chrome` outside the serial tier and a
  `serial` module in `ADMITTED_GIT_TESTS`
- `devtools/run_goldens.py`, `devtools/ci_plan.sh`, `devtools/ci_verdict.sh`,
  `devtools/check_ci.py`, and `devtools/ci_report.py`, each with tests
- `devtools/suite_report.py`: per-module time from a run under xdist, where progress
  lines no longer follow modules
- `.github/workflows/ci.yml` and a new scheduled workflow
- [End-to-End Testing](../../../e2e-testing.md) and
  [development](../../../development.md): the tiers, the targets, and how to add a shard

### API Changes

None. No route, kind, model, or persisted state changes, so the parity registry is
untouched.

## Implementation Plan

The phases are in order of payoff.
Phase 1 changes no workflow file, and the owner’s answer to Q2 admits its dependency.
Phase 2 changes the workflow, which the owner’s answer to Q1 approves through reviewed
pull requests. Phase 3 is independent of both.

### Phase 1: The Suite on Four Processors

Expected: a `test` leg from 17 to 20 minutes to 10.5 to 13 (est.), with the workflow
unchanged, since it calls `make test`.

- [ ] `mb-a1le`: Add the `serial` marker, the `--shard` option, and their gates.
  `make test` still runs everything in one process.
- [ ] `mb-dz35`: Add `pytest-xdist` with its supply-chain review, make the parallel tier
  pass under it, and split `make test` into the three targets.
  This step measures the speedup that the plan assumes.
- [ ] `mb-4ub2`: Add `devtools/run_goldens.py` and run the goldens four files at a time.
- [ ] `mb-tjdq`: Teach `devtools/suite_report.py` to read a run under xdist and the
  golden runner’s times, and update the testing guide.
- [ ] `mb-f0z9`: Add `make ci-report`, which prints job medians and 90th percentiles
  from run data.

### Phase 2: Split Jobs in the Workflow

Expected: a pull request wall clock of 4 to 5 minutes (est.), or about 3 with the unit
jobs split in two. The owner approved these workflow changes on 2026-11-16 (Q1).

- [ ] `mb-oz36`: Split `ci.yml` into `unit`, `goldens`, and `serial` jobs, with the
  serial tier on one interpreter for a pull request and on all four for `main`, no
  `fail-fast`, cancellation of superseded pull request runs, time limits, and `ci-ok`.
- [ ] `mb-to1c`: Add `devtools/check_ci.py` to `make lint-check`.
- [ ] `mb-r283`: Run `stack-integration` by tree identity, as split jobs.
- [ ] `mb-stg2`: Add the nightly workflow: the serial tier five times on `main`, and the
  time-limit report.

### Phase 3: Flakes, Slow Tests, and Path Classes

- [ ] `mb-nx36`: Fix “Chrome wrote no DevTools port” in `tests/dom/chrome-session.mjs`,
  which failed `test_changed_file_rows_chrome.py` twice.
- [ ] `mb-v719`: Fix the stall at `phase keys` in `test_github_pulls_stacks_chrome.py`,
  seen twice, once on `main`.
- [ ] `mb-6nn3`: Reproduce and fix the three flakes seen once: the metadata line in
  `test_nav_metadata_chrome.py`, the `gh` stop in `test_github_pulls.py`, and
  `PrivateStorageError` in `test_github_pull_files.py`.
- [ ] `mb-551m` and `mb-zv5s`, which exist: the navigation reveal and the Chrome session
  that outlives its result.
- [ ] `mb-37dw`: Cut the serial tier’s fixed waits, starting with the three pull-header
  cases at 10.2 seconds each and the 124 seconds of `test_transitions_instrument.py`.
- [ ] `mb-pvyg`: Path classes for documentation-only and macOS-only pull requests, if
  the owner wants them.

## Testing Strategy

Each step is verified by CI’s own run data, read with the commands in the research
brief’s methodology and, once it exists, `make ci-report`.

| Step | Verified by | Accept when |
| --- | --- | --- |
| `serial` marker and `--shard` | `pytest --collect-only` counts for `-m serial`, `-m "not serial"`, and every shard | The two tiers sum to the whole collection, and the shards of each to the tier, at `N` from 1 to 5 |
| xdist | The pull request’s own `test` jobs, rerun until there are 10 runs | No failure that a serial run does not have; the parallel tier at least 2.3 times faster than the 510 to 661 seconds measured. Below that, Phase 2 splits `unit` in two from the start |
| A test that fails only under xdist | The same 10 runs | Fixed, or marked `serial` with the failure recorded beside the marker |
| Concurrent goldens | 10 runs | The 453 commands pass, and each file’s verdict equals a run with `GOLDEN_JOBS=1` |
| The `gh` guard’s summary | A test that makes a guarded `gh` call in a worker | The summary names it |
| Split jobs | 20 pull request runs after the merge | Median push to green at or under 5 minutes, 90th percentile at or under 6, and the test count of `unit` plus `serial` equal to today’s `test` job on the same commit |
| `ci-ok` | A pull request with one deliberately failing shard, closed unmerged | `ci-ok` is red and names it; the other jobs finish |
| Cancellation | Two pushes a minute apart | The first run is cancelled; a `main` run is never cancelled |
| `stack-integration` | A stack behind `main`, one level with it, and one that conflicts | `needed`, `identical`, and `conflict`, each with its summary |
| Nightly soak | One manual run by `workflow_dispatch` | 20 serial shard jobs run and report |
| Flake fixes | The loaded-machine loop that `mb-alff` and `mb-nvo0` used | The failure reproduces before the fix and not in 30 runs after it |
| The whole plan | The research brief’s tables, taken again 7 days after Phase 2 | The goals above |

## Rollout Plan

1. Merge this plan. The owner has answered the questions that Phases 1 and 2 need.
2. Phase 1 lands as a stack of pull requests.
   Each is safe alone: `make test` runs the same tests at every step, and the workflow
   does not change.
3. Phase 2 lands as one pull request to the workflow, reviewed by the owner, then the
   check, the stack change, and the nightly workflow.
   Reverting that one commit restores today’s jobs, since the Makefile’s `make test`
   keeps working throughout.
4. Phase 3’s beads are independent and land as they are ready.
5. The testing guide and the development guide change in the pull request that changes
   the behavior they describe.

## Risks

- **The xdist factor is assumed.** No run under xdist was measured; the research brief
  says why. If it is under 2.3, the `unit` jobs are split in two, which costs four more
  jobs and no coverage.
- **Tests that are sensitive to load.** A test that passes alone and fails beside three
  workers is found by the 10-run step and fixed or marked `serial`. Two modules outside
  the serial tier, `test_cli_main.py` and `test_refresh_signals.py`, probe for a free
  port and then bind it, which two workers can race.
- **Goldens that share state.** If two goldens write one location outside their
  sandboxes, they interfere when concurrent.
  The 10-run comparison finds it, and `GOLDEN_JOBS=1` in its own job still finishes in
  3.3 to 4.3 minutes.
- **The free-threaded build under xdist** is untested here.
- **A timeout under xdist** ends a worker, not the run.
  xdist restarts it and reports the crash; the step checks that the report still names
  the test.
- **More jobs at once.** A push starts 18 jobs where it starts 9 today, each much
  shorter, so the job-minutes in flight fall by about half (est.). Jobs already wait up
  to 8.8 minutes at peak, so the queue time is measured again after Phase 2.
- **The serial tier on three interpreters after the merge.** A regression there reaches
  `main` and is reported minutes later, on the commit that caused it.
- **A red `main` needs a reader.** Today nothing tells anyone; Q6 is open.
  Once the owner’s ruleset requires `ci-ok` (Q5), a red pull request cannot merge, which
  leaves the serial tier on three interpreters as what can turn `main` red.
- **Growth continues.** The Chrome tier went from nothing to 6.3 minutes in five days.
  The shard count and the time limits are how the design absorbs that.
- **A developer machine under xdist** runs one worker per processor, which is heavy
  where several agents share a machine; `PYTEST_WORKERS` lowers it.

## Decisions and Open Questions

The owner answered four of the questions on 2026-11-16.

Decided:

1. **Workflow files (Q1): approved.** Agents may restructure `.github/workflows/ci.yml`
   as [Proposed Workflow](#proposed-workflow) describes and add the nightly soak
   workflow, through reviewed pull requests.
2. **A development dependency (Q2): yes.** `pytest-xdist` 3.8.0 and its requirement
   `execnet` 2.1.2 join the `dev` group under the supply-chain rules, with a review in
   `SUPPLY-CHAIN-SECURITY.md`. Both are MIT-licensed, published 2025-07-01 and
   2025-11-12, and never ship in the wheel.
3. **The serial tier’s interpreters (Q3): one on pull requests, four on `main`.** The
   serial tier runs on Python 3.13 for a pull request and on all four interpreters for
   every push to `main`.
4. **A required check (Q5): yes.** Once Phase 2’s `ci-ok` job exists, the owner sets a
   ruleset that requires it on `main`. It is a repository setting only the owner can
   change. It stops a red pull request from merging and lets auto-merge wait for CI,
   which it cannot do while nothing is required.

Open, with the plan’s recommendation standing as a proposal:

- **`stack-integration`’s record (Q4).** Is the `plan` job’s summary an acceptable
  record of a skipped integration, in place of step gating?
  Phase 2 builds it that way, and its pull request asks again.
- **A red `main` (Q6).** Who is told?
  The merging agent watching the run, as today, or an issue the workflow opens, which
  needs `issues: write` for one job?
  Phase 2 adds no such permission.
- **Path classes (Q7).** Are the light runs of Phase 3 wanted, for 16 percent of pull
  requests?
- **A merge queue (Q8)** is not proposed.
  Whether a repository owned by a user account can enable one was not established, and
  with the matrix at about five minutes little is left for it to move.

## References

- [Why CI Takes Twenty Minutes](../../research/research-2026-11-16-ci-speed.md): the
  measurements, the options, and what was not measured
- [End-to-End Testing](../../../e2e-testing.md): the tiers, skips, timeouts, and
  `make test-report`
- [Supply-Chain Security](../../../../SUPPLY-CHAIN-SECURITY.md): the rules for a
  dependency or an action
- [Agent Instructions](../../../../AGENTS.md): limits are set from measurements, and a
  check is preferred to a sentence
- Beads `mb-h8zb`, and `mb-alff`, `mb-nvo0`, `mb-551m`, and `mb-zv5s` for the flakes
  already traced

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
