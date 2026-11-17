# Plan for Fast CI

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved for Phases 1 and 2. The owner answered Q1, Q2, Q3, and Q5 on
2026-11-16, and answers relayed on 2026-11-17 decide Q6
([Decisions and Open Questions](#decisions-and-open-questions)); Q4, Q7, Q8, and Q9 are
open.
Bead `mb-h8zb` tracks this plan, and each implementation step below is a bead under
it. Nothing here is implemented: no workflow, Makefile target, dependency, or repository
setting has changed.
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
about 3 if the unit job is also split in two, on 39 to 49 runner minutes where a push
uses 84 today.

## Goals

- A pull request to `main` reaches a green or red verdict in 5 minutes or less at the
  median and 6 at the 90th percentile, measured as the research brief measured 20.5 and
  24.4.
- Every check that runs today runs on every commit that reaches `main`, and before the
  merge for all but one, which [How Coverage Is Kept](#how-coverage-is-kept) argues.
- A failure of that one check on `main` stops the next merge until it is fixed.
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
| Most jobs running at once | 40, a ceiling held for over an hour; the Pro plan’s limit is 40 |
| Green run on `main`, by week | 3.1 minutes on 2026-09-14, 22.4 on 2026-11-16 |

## Design

### Approach

Three changes carry the result, and each is independent of the others:

1. **Use the processors.** The modules that do not need a machine to themselves run
   under pytest-xdist, one worker per processor.
   The goldens run several files at a time.
2. **Split by tier.** The suite becomes four tiers in separate jobs: a **parallel tier**
   (unit and route tests), a **serial tier** (tests that time themselves and need the
   machine to themselves, starting with the process-group checks), a **Chrome tier**
   (headless Chrome), and the **goldens**. The Chrome tier is split across runners,
   since it cannot share one.
   The wall clock is then the slowest job, not their sum.
3. **Run each thing as often as it informs.** The Chrome tier runs on one interpreter
   for a pull request and on all four for every commit on `main`, and a red `main` puts
   all four back on every pull request until it is fixed.
   `stack-integration` runs when merging `main` changes the tree.
   A superseded run is cancelled, and a failed leg no longer cancels its siblings.

### Tiers Within `make test`

`make test` stays the definition of the default tier and still runs everything.
It becomes four targets that CI can also run one at a time:

| Target | Runs | How |
| --- | --- | --- |
| `make test-parallel` | every test in neither tier below | `pytest -m "not serial and not chrome" -n auto --dist loadfile` |
| `make test-serial` | the serial tier: tests marked `serial` and not `chrome` | `pytest -m "serial and not chrome"`, one test at a time |
| `make test-chrome` | the Chrome tier: tests marked `chrome` | `pytest -m chrome`, one test at a time |
| `make test-goldens` | `tests/golden/*.tryscript.md` | `devtools/run_goldens.py`, four files at a time |

- **Two markers, for two properties.** Needing the machine to itself and being checked
  on one interpreter are separate claims, so each has its own marker:
  - `serial` means the test measures wall-clock time and needs the machine to itself.
    It says nothing about interpreters, so the serial tier runs on all four before the
    merge. A module adds it by hand, with the measurement that forced it as the marker’s
    reason, as a module raises its timeout today.
    `tests/test_process_group.py` is the first: its process-group, signal, and thread
    checks are the serial tier, and its one Chrome test is in the Chrome tier.
  - `chrome` means the test drives headless Chrome.
    It also needs the machine to itself, and it is the one marker that lets a pull
    request check a test on one interpreter
    ([How Coverage Is Kept](#how-coverage-is-kept)). `tests/conftest.py` gives it to
    every test that uses the `chrome_profile` fixture, so the Chrome tier needs no list,
    and that fixture is its only source.
- **The three pytest targets partition the suite.** Their expressions cover every
  combination of the two markers, so no test is in none of them or in two.
  `tests/suite_gates.py` holds each marker to its meaning, as it fails a module that
  asks for the Git floor from outside `ADMITTED_GIT_TESTS`:
  - a test that asks for Chrome through `require_chrome` and is not `chrome` fails;
  - a test marked `chrome` that does not use `chrome_profile` fails, so no test reaches
    one interpreter by being marked;
  - a `serial` marker without a reason fails.
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
None of them is in the serial or the Chrome tier today, and a gate fails one that joins
either.

### Jobs

For a pull request to `main`:

| Job | Count | What it runs | Minutes each |
| --- | ---: | --- | --- |
| `plan` | 1 | reads whether `main` is red, and decides the Chrome tier’s interpreters and whether `stack-integration` is needed | 0.2 (est.) |
| `lint` | 1 | `make lint-check audit` | 1.5 (measured) |
| `distribution` | 1 | `make build` | 0.7 (measured) |
| `unit` | 4 | `make test-parallel` on 3.12, 3.13, 3.14, and 3.14t | 3.3 to 4.0 on 3.13; 4.0 to 5.0 on 3.14t (est.) |
| `goldens` | 4 | `make test-goldens`, then `make test-serial`, on the same four | 2.5 to 3.2 (est.) |
| `chrome` | 4 | `make test-chrome SHARD=I/4` on 3.13 | 1.9 to 2.4 (est.) |
| `admitted-git` | 2 | `make test-admitted-git` on Git 2.43.7 and 2.50.1 | 2.5 to 3.0 (est.) |
| `ci-ok` | 1 | fails unless every job above succeeded | 0.1 (est.) |

That is 18 jobs and 39 to 49 runner minutes (est.), the sum of each leg’s estimate,
against 9 jobs and 84 today.
The wall clock is the `unit (3.14t)` job’s 4 to 5 minutes (est.). Splitting each `unit`
job in two with `SHARD=I/2` brings it to about 3 minutes; the phase’s measurement
decides, by the rule in [Time Limits](#time-limits).

The estimates divide the measured serial seconds by an assumed 2.5 to 3.2 for four
workers and add 0.4 to 0.6 minutes of setup and worker start.
That factor is the plan’s main unmeasured number; Phase 1 measures it first.

The serial tier rides in the `goldens` job, after the goldens finish, so it has the
machine to itself and adds no job.
It is about a minute, at least 50 of `tests/test_process_group.py`’s 57 seconds on 3.13,
so the job stays shorter than `unit`. In `test (3.13)` of run 44007745684 that module’s
one Chrome test was not among the 25 slowest tests, the last of which took 7.0 seconds.
The Chrome shards’ estimate leaves those seconds out.

A push to `main` runs the same jobs with `chrome` on all four interpreters, 16 jobs in
place of 4 and 30 in all, and never cancels.
A pull request to `main` runs the same 30 while `main` is red
([A Red `main`](#a-red-main)).

### How Coverage Is Kept

| Check today | On a pull request | On every commit on `main` | Why nothing is lost |
| --- | --- | --- | --- |
| `make lint-check audit` | `lint`, unchanged | unchanged | Same commands |
| `make build` | `distribution`, unchanged | unchanged | Same commands |
| pytest, tests in neither tier, on four interpreters | `unit` on four interpreters | same | Same tests and interpreters. With the two tiers, a partition of the suite by two markers |
| pytest, serial tier, on four interpreters | `goldens`, after the goldens, on four interpreters | same | Same tests and interpreters, one at a time |
| pytest, Chrome tier, on 3.13 | `chrome`, four shards | same | Shards partition the tier by construction |
| pytest, Chrome tier, on 3.12, 3.14, and 3.14t | only while `main` is red | `chrome` on all four | See below |
| tryscript goldens on four interpreters | `goldens` on four interpreters | same | Same commands; the runner fails if a file reports no verdict |
| `make test-admitted-git` on two Gits | `admitted-git`, under xdist | same | Same modules, same unpatched floor |
| `stack-integration` | The same targets on the head merged with `main`, when that tree differs from the one the other jobs ran | not applicable | An identical tree is identical input to every check |
| Strict skips | Set for every tier target | same | `STRICT_SKIPS` is on each recipe |
| `macos-app.yml` | unchanged | unchanged | Not touched, and outside `ci-ok` |

**The Chrome tier on three more interpreters** is the one check that moves from before
the merge to after it.
The tier measures layout, paint, and input in Chrome against a server process.
What that server sends on each interpreter is pinned by the route tests and the goldens,
which keep running on all four before the merge, and the tier’s time is the same 6.3
minutes on every interpreter, as a browser-bound tier’s would be.
A regression that only it could catch needs a server difference between interpreters
that no route test or golden pins and that changes what the browser draws.
That is possible, most plausibly on the free-threaded build, so the check is kept: every
commit on `main` runs the tier on all four, and [A Red `main`](#a-red-main) says how a
failure there stops the next merge.
Running it once a push also cuts the chance of a flake failing a healthy run from four
or five draws to one.
The owner chose this on 2026-11-16 (Q3); the alternative keeps all four on pull requests
for 12 more jobs and about 24 more runner minutes a push.

The argument holds for browser-bound tests only, so only the `chrome` marker moves a
test there. A test marked `serial` keeps all four interpreters before the merge,
including the process-group checks, which could differ on the free-threaded build, and
any test marked `serial` because it failed under xdist.

**`devtools/check_ci.py`**, added to `make lint-check`, keeps the table true.
It fails unless:

- the workflow runs each of the four tier targets, and the serial tier on every
  interpreter;
- the shard numbers of each sharded job are `1` through `N`;
- every interpreter list in `ci.yml` matches the classifiers in `pyproject.toml` and the
  free-threaded build: the `unit` and `goldens` matrices and the `plan` job’s `PYTHONS`,
  and `PR_CHROME_PYTHON` is one of them;
- the `chrome` matrix is the `plan` job’s output.

The tests of `devtools/ci_plan.sh` hold that a push to `main`, and a pull request while
`main` is red, get all of `PYTHONS`. `devtools/check_supply_chain.py` already holds the
`admitted-git` matrix to both Git floors.

### A Red `main`

With the Chrome tier on one interpreter before the merge, a regression on another one
reaches `main`. A required `ci-ok` (Q5) alone would not stop the next pull request from
merging on top of it, since that pull request checks the tier on 3.13 only, and a second
regression on the same interpreter would add no new signal.
Two mechanisms close that (Q6):

- **`ci-ok` fails while `main` is red.** The `plan` job of a pull request to `main`
  reads `main`’s state from the Actions API, with `actions: read` on that one job.
  The state is the conclusion of the newest `ci.yml` run of a push to `main`. While that
  run is still going, it is the conclusion of the attempt before it, for a rerun, or of
  the run before it, for a first attempt.
  Only `success` is green; any other conclusion, or no answer, is red.
  - While `main` is red, the `plan` job gives the run `main`’s whole matrix, the Chrome
    tier on all four interpreters, and `ci-ok` names `main`’s red run in its verdict.
  - A pull request whose merge with `main` carries `main`’s failure therefore fails
    `ci-ok`. Only one that repairs it passes, which is how `main` is fixed under a
    required check.
  - Not knowing the state costs runner minutes, never coverage.

- **The merging agent watches `main` after each merge.** It follows the `ci.yml` run of
  the merge commit to its end (`gh run watch`).
  - While that run is red, the agent merges only a pull request whose `ci-ok` ran
    `main`’s whole matrix.
  - It reruns a failure that a bead names as a known flake once, which turns the run
    green if it was the flake.
    Any other failure gets a bead and a fix or a revert.
  - This covers what `ci-ok` cannot: a pull request whose `ci-ok` went green before
    `main` turned red still reads green.

  Phase 2 adds this procedure, with that reason, to the Git section of
  [Agent Instructions](../../../../AGENTS.md#git).

A stacked pull request does not read `main`’s state.
It merges into its base branch, and it reaches `main` through a run whose base is
`main`.

### Stacks

`stack-integration` asks whether the pull request’s head still works once `main` is
merged in. The `plan` job computes that merge with `git merge-tree --write-tree` and
compares its tree with the tree of the merge commit the other jobs check out:

- **Identical:** the other jobs already answer it.
  Nothing more runs, and the `plan` job’s summary names the tree.
- **Different:** seven jobs run on the head merged with that exact `main` commit, on
  Python 3.13 as today: `make lint-check`, `make test-parallel`,
  `make test-goldens test-serial`, and the four Chrome shards.
  Each is 1.5 to 4 minutes (est.), where the single job takes 19.4 today.
- **Conflict:** `ci-ok` fails with today’s message, and the other jobs still run.

Today the job gates its steps, not itself, so that it always reports what it decided.
Here the `plan` job is that report: it always runs, and it writes the event, the base,
both trees, `main`’s state, and its decisions to the job summary.
Gating seven jobs by their steps would start seven runners to say that nothing was
needed. Q4, which is open, asks the owner to accept the change of convention.

Cancelling superseded runs helps stacks most, since a restack pushes every layer at
once.

### Flakes

- **No sibling is cancelled.** With `fail-fast: false`, “Re-run failed jobs” reruns the
  one job that failed, and the legs that passed stay as evidence.
  In the sample, 22 reruns re-executed 70 jobs for 22 single failing tests.
- **One draw a push.** The Chrome tier runs once for a pull request while `main` is
  green.
- **A machine to itself.** The serial and Chrome tiers never run beside xdist workers or
  the goldens.
- **Root fixes.** `mb-alff` and `mb-nvo0` are fixed.
  `mb-551m` and `mb-zv5s` are open, and Phase 3 adds a bead for each flake the sample
  proved that has none.
- **A nightly soak.** A scheduled workflow runs the serial and Chrome tiers five times
  on `main`, on Python 3.13, the interpreter a pull request draws on, and fails on any
  failure, so a flake is found away from a pull request.
  It finds flakes; the runs on each commit of `main` are the coverage.

### Time Limits

Each job gets a `timeout-minutes` set at about 1.5 times its measured 90th percentile,
with the measurement in a comment beside it, as
[Values live in code](../../../development.md#documentation) asks of every limit.
That is also the “measure before bounding” rule of
[Agent Instructions](../../../../AGENTS.md#browser-and-plugin-boundary).
Run-to-run variation for one commit was about 20 percent in the sample, so the limit
does not trip on a slow runner.
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
3.13. No Chrome-tier or `admitted-git` module reads those paths, and the `unit` and
`goldens` jobs run every test that does.
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

# A CI job calls each tier target directly, so each installs first, as `test` does.
.PHONY: test-parallel test-serial test-chrome test-goldens
test-parallel test-serial test-chrome test-goldens: | install

# The default tier, as four parts that CI also runs as separate jobs.
test: test-parallel test-serial test-chrome test-goldens

test-parallel:
	$(PYTEST) -m "not serial and not chrome" -n $(PYTEST_WORKERS) --dist loadfile

test-serial:
	$(PYTEST) -m "serial and not chrome"

test-chrome:
	$(PYTEST) -m chrome

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
    # The one job that reads other runs: main's newest ci.yml run (A Red main).
    permissions:
      contents: read
      actions: read
    outputs:
      chrome-pythons: ${{ steps.decide.outputs.chrome-pythons }}
      integration: ${{ steps.decide.outputs.integration }}
      main-sha: ${{ steps.decide.outputs.main-sha }}
      main-state: ${{ steps.decide.outputs.main-state }}
      main-run: ${{ steps.decide.outputs.main-run }}
    steps:
      - setup: checkout only
      - id: decide
        env:
          EVENT: ${{ github.event_name }}
          BASE: ${{ github.event.pull_request.base.ref }}
          HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          REPO: ${{ github.repository }}
          GH_TOKEN: ${{ github.token }}
          # Every interpreter main runs each tier on, and the one a pull request runs the
          # Chrome tier on. check_ci.py holds both, and the unit and goldens matrices, to
          # pyproject.toml's classifiers and the free-threaded build.
          PYTHONS: '["3.12","3.13","3.14","3.14t"]'
          PR_CHROME_PYTHON: "3.13"
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
    name: goldens and serial (${{ matrix.python-version }})
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.12", "3.13", "3.14", "3.14t"]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - setup
      - run: make test-goldens
      # After the goldens, so the serial tier has the machine to itself; it runs when a
      # golden failed too, so the job reports both.
      - if: ${{ !cancelled() }}
        run: make test-serial

  chrome:
    needs: plan
    name: chrome (${{ matrix.python-version }}, ${{ matrix.shard }}/4)
    strategy:
      fail-fast: false
      matrix:
        # PR_CHROME_PYTHON for a pull request while main is green; PYTHONS otherwise.
        python-version: ${{ fromJSON(needs.plan.outputs.chrome-pythons) }}
        shard: [1, 2, 3, 4]
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - setup
      - run: make test-chrome SHARD=${{ matrix.shard }}/4

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
          - test-goldens test-serial
          - test-chrome SHARD=1/4
          - test-chrome SHARD=2/4
          - test-chrome SHARD=3/4
          - test-chrome SHARD=4/4
    runs-on: ubuntu-latest
    timeout-minutes: 8
    steps:
      - setup: checkout the pull request's head, Python 3.13
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git merge --no-edit ${{ needs.plan.outputs.main-sha }}
      - run: make ${{ matrix.part }}

  ci-ok:
    if: always()
    needs: [plan, lint, distribution, unit, goldens, chrome, admitted-git, stack-integration]
    runs-on: ubuntu-latest
    timeout-minutes: 2
    steps:
      - setup: checkout only
      - env:
          RESULTS: ${{ toJSON(needs) }}
          INTEGRATION: ${{ needs.plan.outputs.integration }}
          MAIN_STATE: ${{ needs.plan.outputs.main-state }}
          MAIN_RUN: ${{ needs.plan.outputs.main-run }}
        run: bash devtools/ci_verdict.sh
```

`devtools/ci_plan.sh` holds the decision, so that it has tests:

```bash
main_state=none
if [ "$EVENT" = pull_request ] && [ "$BASE" = main ]; then
  # "green <run>" or "red <run>", by the rule in A Red main. A failed read is red.
  main=$(main_state_from_api) || main="red unknown"
  main_state=${main%% *} main_run=${main#* }
fi
if [ "$EVENT" = pull_request ] && [ "$main_state" != red ]; then
  chrome="[\"$PR_CHROME_PYTHON\"]"
else
  chrome=$PYTHONS # a push to main, or a pull request while main is red
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
While `MAIN_STATE` is `red`, it names `MAIN_RUN` in its verdict, so a red `ci-ok` says
whether `main` was already red.

No new action is used, and `gh` is the runner’s own.
The `plan` job is the only one with a permission beyond `contents: read`. The scheduled
workflow of Phase 2 uses the same pinned actions.

### Components

- `Makefile`: the tier targets and their variables
- `pyproject.toml` and `uv.lock`: `pytest-xdist` in the `dev` group, with `execnet`
- `SUPPLY-CHAIN-SECURITY.md`: the review of those two, and of the `plan` job’s
  `actions: read`
- `tests/conftest.py`: the `serial` and `chrome` markers, the `--shard` option, and the
  `gh` guard’s summary reading every worker’s log
- `tests/suite_gates.py`: the gates for `require_chrome` outside the Chrome tier, a
  `chrome` marker without `chrome_profile`, a `serial` marker without a reason, and a
  `serial` or `chrome` test in `ADMITTED_GIT_TESTS`
- `devtools/run_goldens.py`, `devtools/ci_plan.sh`, `devtools/ci_verdict.sh`,
  `devtools/check_ci.py`, and `devtools/ci_report.py`, each with tests
- `devtools/suite_report.py`: per-module time from a run under xdist, where progress
  lines no longer follow modules
- `.github/workflows/ci.yml` and a new scheduled workflow
- `AGENTS.md`: the merge procedure of [A Red `main`](#a-red-main) in its Git section
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

- [ ] `mb-a1le`: Add the `serial` and `chrome` markers, the `--shard` option, and their
  gates. `make test` still runs everything in one process.
- [ ] `mb-dz35`: Add `pytest-xdist` with its supply-chain review, make the parallel tier
  and `make test-admitted-git` pass under it, and split `make test` into the four
  targets. This step measures the speedup that the plan assumes.
- [ ] `mb-4ub2`: Add `devtools/run_goldens.py` and run the goldens four files at a time.
- [ ] `mb-tjdq`: Teach `devtools/suite_report.py` to read a run under xdist and the
  golden runner’s times, and update the testing guide.
- [ ] `mb-f0z9`: Add `make ci-report`, which prints job medians and 90th percentiles
  from run data.

### Phase 2: Split Jobs in the Workflow

Expected: a pull request wall clock of 4 to 5 minutes (est.), or about 3 with the unit
jobs split in two. The owner approved these workflow changes on 2026-11-16 (Q1).

- [ ] `mb-oz36`: Split `ci.yml` into `unit`, `goldens`, and `chrome` jobs, with the
  serial tier in `goldens` on every interpreter, and the Chrome tier on one interpreter
  for a pull request and on all four for `main` and while `main` is red.
  It also turns `fail-fast` off, cancels superseded pull request runs, and adds time
  limits, `ci-ok`, and the merge procedure in `AGENTS.md`.
- [ ] `mb-to1c`: Add `devtools/check_ci.py` to `make lint-check`.
- [ ] `mb-r283`: Run `stack-integration` by tree identity, as split jobs.
- [ ] `mb-stg2`: Add the nightly workflow: the serial and Chrome tiers five times on
  `main`, and the time-limit report.

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
- [ ] `mb-37dw`: Cut the Chrome tier’s fixed waits, starting with the three pull-header
  cases at 10.2 seconds each and the 124 seconds of `test_transitions_instrument.py`.
- [ ] `mb-pvyg`: Path classes for documentation-only and macOS-only pull requests, if
  the owner wants them.

## Testing Strategy

Each step is verified by CI’s own run data, read with the commands in the research
brief’s methodology and, once it exists, `make ci-report`.

| Step | Verified by | Accept when |
| --- | --- | --- |
| The markers and `--shard` | `pytest --collect-only` counts for the three tier expressions and for every shard | The three tiers sum to the whole collection, and the shards of each to the tier, at `N` from 1 to 5 |
| The marker gates | A test for each gate with a module that breaks it | Each fails with the gate’s reason |
| xdist | The pull request’s own `test` jobs, rerun until there are 10 runs | No failure that a serial run does not have; the parallel tier at least 2.3 times faster than the 510 to 661 seconds measured. Below that, Phase 2 splits `unit` in two from the start |
| A test that fails only under xdist | The same 10 runs | Fixed, or marked `serial` with the failure as the marker’s reason, which keeps it on every interpreter |
| `make test-admitted-git` under xdist | The pull request’s `admitted-git` jobs over the same 10 runs | Both Git legs green in all 10, with the test count of a serial run of `ADMITTED_GIT_TESTS` on the same commit |
| Concurrent goldens | 10 runs | The 453 commands pass, and each file’s verdict equals a run with `GOLDEN_JOBS=1` |
| The `gh` guard’s summary | A test that makes a guarded `gh` call in a worker | The summary names it |
| Split jobs | 20 pull request runs after the merge | Median push to green at or under 5 minutes, 90th percentile at or under 6, and `unit`, the serial tier, and `chrome` together collecting the tests today’s `test` job collects on the same commit |
| `ci-ok` | A pull request with one deliberately failing shard, closed unmerged | `ci-ok` is red and names it; the other jobs finish |
| `main`’s state | `devtools/ci_plan.sh`’s tests over recorded API answers: success, failure, cancelled, no run, a failed read, a first attempt in progress, and a rerun in progress | Only `success`, read by the rule in [A Red `main`](#a-red-main), keeps the Chrome tier on `PR_CHROME_PYTHON`; every other answer gives it all of `PYTHONS` |
| A red `main` in CI | The first pull request run after `main` is next red | The run has the Chrome tier on all four, and `ci-ok`’s verdict names `main`’s run |
| Cancellation | Two pushes a minute apart | The first run is cancelled; a `main` run is never cancelled |
| `stack-integration` | A stack behind `main`, one level with it, and one that conflicts | `needed`, `identical`, and `conflict`, each with its summary |
| Nightly soak | One manual run by `workflow_dispatch` | 5 serial-tier jobs and 20 Chrome shard jobs run and report |
| Flake fixes | The loaded-machine loop that `mb-alff` and `mb-nvo0` used | The failure reproduces before the fix and not in 30 runs after it |
| The whole plan | The research brief’s tables, taken again 7 days after Phase 2 | The goals above |

## Rollout Plan

1. Merge this plan. The owner has answered the questions that Phases 1 and 2 need.
2. Phase 1 lands as a stack of pull requests.
   Each is safe alone: `make test` runs the same tests at every step, and the workflow
   does not change.
3. Phase 2 lands as one pull request to the workflow, reviewed by the owner, with the
   merge procedure in `AGENTS.md`; then the check, the stack change, and the nightly
   workflow. From that merge on, the merging agent watches `main` after each merge.
   Reverting that one commit restores today’s jobs, since the Makefile’s `make test`
   keeps working throughout.
4. Once `ci-ok` exists, the owner sets the ruleset that requires it (Q5).
5. Phase 3’s beads are independent and land as they are ready.
6. The testing guide and the development guide change in the pull request that changes
   the behavior they describe.

## Risks

- **The xdist factor is assumed.** No run under xdist was measured; the research brief
  says why. If it is under 2.3, the `unit` jobs are split in two, which costs four more
  jobs and no coverage.
- **Tests that are sensitive to load.** A test that passes alone and fails beside three
  workers is found by the 10-run step, and fixed or marked `serial`, which keeps it on
  every interpreter. Two modules outside the Chrome tier, `test_cli_main.py` and
  `test_refresh_signals.py`, probe for a free port and then bind it, which two workers
  can race.
- **A growing serial tier.** Each test marked `serial` adds its time to every `goldens`
  job. The job’s time limit reports that growth, and fixing the race is the remedy before
  marking.
- **Goldens that share state.** If two goldens write one location outside their
  sandboxes, they interfere when concurrent.
  The 10-run comparison finds it, and `GOLDEN_JOBS=1` in its own job still finishes in
  3.3 to 4.3 minutes.
- **The free-threaded build under xdist** is untested here.
- **A timeout under xdist** ends a worker, not the run.
  xdist restarts it and reports the crash; the step checks that the report still names
  the test.
- **More jobs at once.** A pull request run starts 18 jobs where it starts 9 today, and
  a push to `main` 30, each much shorter, so the job-minutes in flight fall by about
  half (est.). The sample’s running jobs never passed 40, the Pro plan’s limit, so two
  or three runs at once now reach it.
  Jobs already wait up to 8.8 minutes at peak, so the queue time is measured again after
  Phase 2. If it costs the goal, `main`’s 16 Chrome jobs are the lever: two shards an
  interpreter would leave `unit` as `main`’s longest job (est.).
- **The Chrome tier on three interpreters after the merge.** A regression there reaches
  `main`. The merging agent sees it when that run ends, and until `main` is green,
  `ci-ok` fails every pull request that does not fix it.
- **A red `main` costs every pull request.** While `main` is red, each pull request run
  is 30 jobs, not 18, and draws the Chrome tier four times.
  A red `main` from a flake is therefore rerun when the merging agent sees it.
- **A `ci-ok` that went green before `main` turned red** still reads green.
  The merge procedure covers it for agents; a merge by hand is not covered.
- **Growth continues.** The Chrome tier went from nothing to 6.3 minutes in five days.
  The shard count and the time limits are how the design absorbs that.
- **A developer machine under xdist** runs one worker per processor, which is heavy
  where several agents share a machine; `PYTEST_WORKERS` lowers it.

## Decisions and Open Questions

The owner answered four of the questions on 2026-11-16, and the answers relayed on
2026-11-17 decide a fifth.

Decided:

1. **Workflow files (Q1): approved.** Agents may restructure `.github/workflows/ci.yml`
   as [Proposed Workflow](#proposed-workflow) describes and add the nightly soak
   workflow, through reviewed pull requests.
2. **A development dependency (Q2): yes.** `pytest-xdist` 3.8.0 and its requirement
   `execnet` 2.1.2 join the `dev` group under the supply-chain rules, with a review in
   `SUPPLY-CHAIN-SECURITY.md`. Both are MIT-licensed, published 2025-07-01 and
   2025-11-12, and never ship in the wheel.
3. **The browser tier’s interpreters (Q3): one on pull requests, four on `main`.** As
   asked on 2026-11-16, the tier that needs a machine to itself runs on Python 3.13 for
   a pull request and on all four interpreters for every push to `main`. On 2026-11-17
   that rule was narrowed to the tests that use `chrome_profile`, the Chrome tier; the
   serial tier runs on all four before the merge.
4. **A required check (Q5): yes.** Once Phase 2’s `ci-ok` job exists, the owner sets a
   ruleset that requires it on `main`. It is a repository setting only the owner can
   change. It stops a pull request with a red `ci.yml` run from merging and lets
   auto-merge wait for CI, which it cannot do while nothing is required.
   `macos-app.yml` is a separate, path-filtered workflow outside `ci-ok`, so a red macOS
   job still does not block a merge.
5. **A red `main` (Q6), 2026-11-17.** `ci-ok` fails while `main` is red, and the merging
   agent watches `main` after each merge, as [A Red `main`](#a-red-main) describes.
   The `plan` job gets `actions: read`; no job gets `issues: write`.

Open, with the plan’s recommendation standing as a proposal:

- **`stack-integration`’s record (Q4).** Is the `plan` job’s summary an acceptable
  record of a skipped integration, in place of step gating?
  Phase 2 builds it that way, and its pull request asks again.
- **Path classes (Q7).** Are the light runs of Phase 3 wanted, for 16 percent of pull
  requests?
- **A merge queue (Q8)** is not proposed.
  Whether a repository owned by a user account can enable one was not established, and
  with the matrix at about five minutes little is left for it to move.
- **A red nightly soak (Q9).** Who reads it?
  A red nightly does not make `main` red, since `ci-ok` reads only `ci.yml` runs.
  The proposal: the merging agent reads the newest nightly run when it starts merging,
  and gives each failure it names a bead.

## References

- [Why CI Takes Twenty Minutes](../../research/research-2026-11-16-ci-speed.md): the
  measurements, the options, and what was not measured
- [End-to-End Testing](../../../e2e-testing.md): the tiers, skips, timeouts, and
  `make test-report`
- [Supply-Chain Security](../../../../SUPPLY-CHAIN-SECURITY.md): the rules for a
  dependency, an action, or a permission
- [Agent Instructions](../../../../AGENTS.md): bounds are set from measurements, a check
  is preferred to a sentence, and the Git section holds the merge procedure
- [Development](../../../development.md#documentation): a limit is documented beside its
  constant, with the measurement that set it
- Beads `mb-h8zb`, and `mb-alff`, `mb-nvo0`, `mb-551m`, and `mb-zv5s` for the flakes
  already traced

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
