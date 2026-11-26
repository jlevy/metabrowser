# Plan for Fast CI

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved for Phases 1 and 2. The owner answered Q1, Q2, Q3, and Q5 on
2026-11-16, and answers relayed on 2026-11-17 decide Q6
([Decisions and Open Questions](#decisions-and-open-questions)). On 2026-11-17 the owner
also decided Q4, on review A8 of #504, and extended Q6 to stacked pull requests, on
review A3; Q7, Q8, and Q9 are open.
Bead `mb-h8zb` tracks this plan, and each implementation step below is a bead under it.
Phase 1 is implemented by jlevy/metabrowser#499: the tier targets, the golden runner,
the reports, and pytest-xdist.
Phase 2 is implemented by jlevy/metabrowser#504: the split workflow with `ci-ok`, the
nightly soak, and `devtools/check_ci.py`. No repository setting has changed; the ruleset
that requires `ci-ok` is the owner’s (Q5). The first step of each phase replaces that
phase’s estimates with measurements; an estimate is marked “est.”
Phase 1’s are in [Phase 1 Measurements](#phase-1-measurements): the parallel tier ran
2.0 to 2.2 times faster on four workers, under the 2.3 the estimates assumed on all four
interpreters.

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
- While that one check is red on `main`, a pull request merges only by passing `main`’s
  whole matrix on a tree that contains the failure.
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

  *2026-11-22: superseded (bead `mb-j5j2`).* Both reasons stopped holding.
  One Chrome test grew to 94 seconds, so rank in node-ID order put 360 of the Chrome
  tier’s 790 seconds of tests in one part of four (run 45062416967), and the nightly
  soak’s `make ci-report --check` failed on that part, on the first goldens part, which
  a golden’s size no longer balanced (568 seconds of 844), and on a `unit` part.
  A stand-in for a unit’s time drifts from it as the suite changes, so the parts are now
  dealt by the seconds CI measured: `devtools/shard_weights.py` deals each tier heaviest
  first to the lightest part, from a committed record that `make shard-weights`
  refreshes from a run’s logs.
  The parts are still disjoint and cover the tier by construction, and the same in every
  process, since they depend only on the tests selected and the committed record.
  Replaying that run’s times through the new deal gives Chrome parts of 196 to 200
  seconds of tests where they were 120 to 328.

- **`devtools/run_goldens.py`** runs one `tryscript run <file>` per golden from a queue
  of four workers, prints each file’s output whole, records each file’s time, and fails
  unless every file of the glob reported a verdict.
  The commands and the environment are the ones the `TRYSCRIPT` variable sets today.

`make test-admitted-git` runs its modules under xdist as well.
None of them is in the serial or the Chrome tier today, and a gate fails one that joins
either.

### Jobs

*2026-11-22: for a pull request while `main` is green,
[The Pull-Request Path](#the-pull-request-path) supersedes this table.*

For a pull request to `main`:

| Job | Count | What it runs | Minutes each |
| --- | ---: | --- | --- |
| `plan` | 1 | reads whether `main` is red, and decides the Chrome tier’s interpreters and whether `stack-integration` is needed | 0.2 (est.) |
| `lint` | 1 | `make lint-check audit` | 1.5 (measured) |
| `distribution` | 1 | `make build` | 0.7 (measured) |
| `unit` | 8 | `make test-parallel SHARD=I/2` on 3.12, 3.13, 3.14, and 3.14t | 1.9 to 4.7 (measured; proposed as 4 unsharded jobs at 3.1 to 5.0, est.) |
| `goldens` | 8 | `make test-goldens SHARD=I/2`, then `make test-serial SHARD=I/2`, on the same four | 3.4 (est.; one job per interpreter took 5.0 to 5.8 at the 90th percentile once the goldens grew to 119 files) |
| `chrome` | 4 | `make test-chrome SHARD=I/4` on 3.13 | 1.9 to 2.4 (est.) |
| `admitted-git` | 2 | `make test-admitted-git` on Git 2.43.7 and 2.50.1 | 2.5 to 3.0 (est.) |
| `ci-ok` | 1 | fails unless every job above succeeded | 0.1 (est.) |

That is 26 jobs, against 9 today.
The proposal had 18, with `unit` unsharded at an estimated wall clock of 4 to 5 minutes;
Phase 1’s measurement split it in two, by the rule in [Time Limits](#time-limits), and
[Phase 2 Measurements](#phase-2-measurements) has the times.

The estimates divide the measured serial seconds by an assumed 2.5 to 3.2 for four
workers and add 0.4 to 0.6 minutes of setup and worker start.
That factor was the plan’s main unmeasured number.
Phase 1 measured 2.0 to 2.2 ([Phase 1 Measurements](#phase-1-measurements)), so the job
times above are optimistic.

The serial tier rides in the `goldens` job, after the goldens finish, so it has the
machine to itself and adds no job.
It is about a minute, at least 50 of `tests/test_process_group.py`’s 57 seconds on 3.13,
so the job stays shorter than `unit`. In `test (3.13)` of run 44007745684 that module’s
one Chrome test was not among the 25 slowest tests, the last of which took 7.0 seconds.
The Chrome shards’ estimate leaves those seconds out.

A push to `main` runs the same jobs with `chrome` on all four interpreters, 16 jobs in
place of 4 and 34 in all, and never cancels.
A pull request runs the same 34 while `main` is red ([A Red `main`](#a-red-main)).

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
- the `chrome` matrix is the `plan` job’s output;
- the `plan` job checks out with `fetch-depth: 0`, which `tests-red` and
  `git merge-tree` need;
- no workflow runs on `pull_request_target`.

Review A1 of #504 found edits that passed those rules and still dropped a check: a fixed
`SHARD`, a matrix `exclude`, a step or job allowed to fail or skipped, a deleted `lint`,
`distribution`, or `stack-integration` job, a dropped `audit`, and a dropped `push`
trigger. The check now fails each, and review B2 added every spelling of the event and
every workflow’s write permissions.
Review C of #504 added a condition on a step it does not belong to, a `make` option or
variable, a `ci-ok` step other than `devtools/ci_verdict.sh` on every job’s result, the
event in another case or past a `}}` in a quoted string, and `env` in a `run:` line.
Its docstring lists the rules, and `tests/test_check_ci.py` breaks each one.

The tests of `devtools/ci_plan.sh` hold that a push to `main`, and a pull request while
`main` is red, get all of `PYTHONS`. `devtools/check_supply_chain.py` already holds the
`admitted-git` matrix to both Git floors.

### A Red `main`

With the Chrome tier on one interpreter before the merge, a regression on another one
reaches `main`. A required `ci-ok` (Q5) alone would not stop the next pull request from
merging on top of it, since that pull request checks the tier on 3.13 only, and a second
regression on the same interpreter would add no new signal.
Two mechanisms close that for every merge an agent makes (Q6):

- **A red `main` widens the next pull request’s run.** The `plan` job of a pull request
  to `main`, and of any other pull request whose tested merge commit contains `main`’s
  head, reads `main`’s state from the Actions API, with `actions: read` on that one job.
  It reads one page of `ci.yml`’s push runs on `main`, newest first, and the first run
  with a completed attempt gives the state.
  A run whose latest attempt has any status other than `completed` (in progress, queued,
  waiting, requested, or pending) counts by the attempt before it, for a rerun, and is
  passed over, for a first attempt.
  Only `success` is green; any other conclusion, or no completed attempt in the page, is
  red. [Testing Strategy](#testing-strategy) lists the result for each kind of run.
  - While `main` is red, the `plan` job gives the run `main`’s whole matrix, the Chrome
    tier on all four interpreters.
  - `ci-ok` still fails only when one of the run’s own jobs fails.
    A pull request whose merge with `main` carries a lasting failure fails it, and only
    one that repairs it passes, which is how `main` is fixed under a required check.
  - The `plan` job also checks whether the merge commit the run tests contains the head
    of the `main` run it read (`git merge-base --is-ancestor`), and writes the reason
    for a `no` to its summary.
  - While `main` is red, `ci-ok` writes its verdict as one line in a fixed format,
    `main-red run=<id> head=<sha> tested=<yes|no>`, to its log and as a `::notice::`
    annotation. It is read from the `ci-ok` job’s own log, since any job of the run can
    print a line like it (review B1 of #504). `tested=yes` means this run ran `main`’s
    whole matrix on a merge commit that contains that head.
    The tests of `ci_verdict.sh` pin the format.
  - Not knowing the state costs runner minutes, never coverage.

- **The merging agent merges by `main`’s state.** Phase 2 adds the procedure to the Git
  section of [Agent Instructions](../../../../AGENTS.md#git), which owns its text: merge
  only once the latest attempt of `main`’s newest `ci.yml` push run has completed, and
  while it is not green, only a pull request whose `ci-ok` passed and wrote `tested=yes`
  with that run’s head.
  Its reason, which the procedure states: `ci-ok` cannot see a pull request whose run
  went green before `main` turned red, or a `main` run that has not completed.
  The head comparison is what makes a verdict current: a verdict names the head that was
  red when its run was planned, and `main` may have moved since.
  Reviews A and B of #504 added where the line is read, a check by hand when the diff
  changes the files that write it, the stacked case, and the reasons for the flake and
  auto-merge rules.

**A stacked pull request reads `main`’s state when the commit it tests contains `main`’s
head**, the owner’s decision of 2026-11-17 on review A3 of #504. A formal GitHub stack’s
merge ref merges the head into its base merged with `main`
([Phase 2 Measurements](#phase-2-measurements)), so each of its layers gets the wide
matrix and a verdict line, and qualifies as a pull request to `main` does;
`gh stack merge` lands every layer below its target, so each must.
A layer of an informal chain, whose merge ref holds the branch below alone, does not
read it, and qualifies once its branch is updated from `main`. The proposal had no
stacked pull request read `main`’s state, which left a formal stack no way to merge
while `main` is red.

### Stacks

`stack-integration` asks whether the pull request’s head still works once `main` is
merged in.
A formal GitHub stack’s merge ref already merges the head into its base merged
with `main`: run 44038762653 of #504 tested `Merge 6dfc1ae5 into 20686e6c`, itself
`Merge de96415a into e442ed10`, `main`’s head then.
So the `plan` job first asks whether the commit the other jobs check out contains
`main`’s head (`git merge-base --is-ancestor`), and otherwise computes the merge with
`git merge-tree --write-tree` and compares its tree with that commit’s:

- **Contained:** the other jobs already check the head with `main` and every layer below
  it. Merging `main` into the head alone would check a subset of that, which never lands,
  so nothing more runs (review A7 of #504).
- **Identical:** the other jobs already answer it.
  Nothing more runs, and the `plan` job’s summary names the tree.
- **Different:** eight jobs run on the head merged with that exact `main` commit, on
  Python 3.13 as today: `make lint-check`, `make test-parallel` in its two parts,
  `make -k test-goldens test-serial`, and the four Chrome shards.
  Each took 1.2 to 4.3 minutes ([Phase 2 Measurements](#phase-2-measurements)), where
  the single job takes 19.4 today.
- **Conflict:** `ci-ok` fails with today’s message, and the other jobs still run.

So `different` and `conflict` now come from an informal chain, whose merge ref holds the
branch below alone, and from a formal stack’s run planned once `main` has moved past the
commit its merge ref holds, as a full rerun can be, which reads no `main` state and
writes no verdict line, so a red `main` still refuses its merge (review C7 of #504). A
formal stack that conflicts with `main` may get no merge ref, and then no `pull_request`
run at all; `mb-ohsk` checks it.

Before this, the job gated its steps, not itself, so that it always reported what it
decided.
Here the `plan` job is that report: it always runs, and it writes the event, the
base, both trees, `main`’s state, and its decisions to the job summary.
`ci-ok`, the required check, also says why it accepted a skipped `stack-integration`.
Gating eight jobs by their steps would start eight runners to say that nothing was
needed.
Q4 is decided: the owner accepted the summary, with `ci-ok`’s line, as the record
on 2026-11-17 (review A8 of #504).

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

The `unit` jobs start split in two with `SHARD=I/2`, since Phase 1 measured the parallel
tier whole at a median over the 4.5 minutes that splits it, on every interpreter
([Phase 1 Measurements](#phase-1-measurements)). Each part holds whole files
(`--shard-by=file`), as a worker does.

### Path Classes

*2026-11-22: decided for the Chrome tier, differently.*
[The Pull-Request Path](#the-pull-request-path) skips the Chrome tier by the paths a
change touches; the light class below, which would also skip `admitted-git` and three
interpreters, was not built, since every pull request now runs one interpreter.

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
      main-run-sha: ${{ steps.decide.outputs.main-run-sha }}
      tests-red: ${{ steps.decide.outputs.tests-red }}
    steps:
      # Today's checkout with fetch-depth: 0. tests-red and git merge-tree need the full
      # history, and check_ci.py holds it on this job.
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
          - -k test-goldens test-serial # -k reports both, as the goldens job does
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
          MAIN_RUN_SHA: ${{ needs.plan.outputs.main-run-sha }}
          TESTS_RED: ${{ needs.plan.outputs.tests-red }}
        run: bash devtools/ci_verdict.sh
```

`devtools/ci_plan.sh` holds the decision, so that it has tests:

```bash
main_state=none tests_red=no why=
if [ "$EVENT" = pull_request ] && [ "$BASE" = main ]; then
  # "<green|red> <run id> <head sha>", by the rule in A Red main.
  if main=$(main_state_from_api); then
    read -r main_state main_run main_run_sha <<<"$main"
  else
    main_state=red why="main's state could not be read"
  fi
  if [ "$main_state" = red ] && [ -z "$why" ]; then
    # Whether the merge commit this run tests contains the head of main's red run.
    # Exit 1 is "not an ancestor"; anything else, such as 128, is a missing commit.
    git merge-base --is-ancestor "$main_run_sha" HEAD && rc=0 || rc=$?
    case $rc in
      0) tests_red=yes ;;
      1) why="the merge commit this run tests predates $main_run_sha" ;;
      *) why="git merge-base exited $rc: $main_run_sha is missing from the clone"
         echo "::warning::tests-red is no because $why" ;;
    esac
  fi
  if [ "$main_state" = green ]; then
    main_run_sha= # named only while main is red
  fi
  echo "main: $main_state $main_run_sha tests-red=$tests_red ${why:+($why)}" >>"$GITHUB_STEP_SUMMARY"
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
While `MAIN_STATE` is `red`, it writes the verdict line of [A Red `main`](#a-red-main)
from `MAIN_RUN`, `MAIN_RUN_SHA`, and `TESTS_RED`, to its log and as a `::notice::`. It
never fails on `MAIN_STATE` alone, which would deadlock a red `main`.

Under `pull_request`, the workflow, `ci_plan.sh`, and `ci_verdict.sh` come from the pull
request’s own merge commit, so the `main`-state read and `ci-ok` bind an honest pull
request, and a change to any of the three is reviewed as a change to the gate.
The workflow stays on `pull_request` and never uses `pull_request_target`, which would
run with the base repository’s token; `check_ci.py` holds that.

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
unchanged, since it calls `make test`. Measured: 14.3 to 15.7 minutes at the median, so
the estimate was missed ([Phase 1 Measurements](#phase-1-measurements)). The Chrome
tier, which this phase does not change, is the larger part of each leg, at 351 to 467 s;
the top of that range came after `main` gained an 85-second Chrome test.
The parallel tier’s factor, 2.0 to 2.2 against the 2.5 to 3.2 the estimate assumed,
accounts for the rest.

- [x] `mb-a1le`: Add the `serial` and `chrome` markers, the `--shard` option, and their
  gates. `make test` still runs everything in one process.
- [x] `mb-dz35`: Add `pytest-xdist` with its supply-chain review, make the parallel tier
  and `make test-admitted-git` pass under it, and split `make test` into the four
  targets. This step measures the speedup that the plan assumes.
- [x] `mb-4ub2`: Add `devtools/run_goldens.py` and run the goldens four files at a time.
- [x] `mb-tjdq`: Teach `devtools/suite_report.py` to read a run under xdist and the
  golden runner’s times, and update the testing guide.
- [x] `mb-f0z9`: Add `make ci-report`, which prints job medians and 90th percentiles
  from run data.

#### Phase 1 Measurements

Taken on 2026-11-17 from the green CI runs of jlevy/metabrowser#499: the three attempts
of run 44026747033 at `d5a05e20`, and runs 44041121764 and 44043995823 at `dbcfd321` and
`5c9365cc`, each on `main` as it then stood.
pytest-xdist started four workers on every leg (`PYTEST_WORKERS=logical`).

The parallel tier, in seconds.
The baseline is the same modules’ time in one process, read by
`devtools/suite_report.py` from the logs of eight green `main` runs, 43956278180 to
44007745684, and summed over the modules the tier selects:

| Leg | Under xdist, five runs | Median | In one process on `main`, median of 8 | Factor |
| --- | --- | ---: | ---: | ---: |
| 3.12 | 243, 296, 311, 260, 299 | 296 | 590 | 2.0 |
| 3.13 | 194, 296, 299, 282, 205 | 282 | 611 | 2.2 |
| 3.14 | 279, 198, 295, 277, 259 | 277 | 604 | 2.2 |
| 3.14t | 239, 275, 344, 297, 353 | 297 | 663 | 2.2 |

- **The factor is below the 2.3 that [Testing Strategy](#testing-strategy) sets** on
  every interpreter, so by that row Phase 2 splits the `unit` jobs in two from the
  start.
- **The limit is the runner, not the schedule.** The tests’ own times, summed by
  `--file-durations`, came to 3.4 to 3.6 times each session’s wall clock, so four
  workers were busy for most of the run.
  The same tests took 1.1 to 1.9 times as long as their median in one process: they
  contend for the runner’s processors, with the Git, Node, and `metab` processes they
  start.
- **Run-to-run variation is large.** One leg’s runs differed by up to 54 percent, as the
  serial baseline’s runs differed by up to 46 percent.
  The 10 runs the Testing Strategy asks for were not taken; five were.

The rest of the `test` leg, in seconds over the same runs: the serial tier 55 to 57; the
Chrome tier 351 to 386, and 443 to 466 once `main` gained an 85-second Chrome test; and
the goldens 73 to 131, against 197 to 258 one at a time.

`make ci-report` in minutes, over #499’s runs and the last 25 push runs of `main`:

| Job | #499, median of its successful jobs | `main`, median |
| --- | ---: | ---: |
| `test (3.12)` | 14.8 | 20.1 |
| `test (3.13)` | 14.3 | 21.4 |
| `test (3.14)` | 14.3 | 20.8 |
| `test (3.14t)` | 15.7 | 22.2 |
| `admitted-git (2.43.7)` | 3.2 | 6.4 |
| `admitted-git (2.50.1)` | 3.5 | 6.6 |

Its three green first attempts reached green a median of 17.1 minutes after their push,
on 70.3 runner minutes, against `main`’s 22.9 and 99.2. Both `admitted-git` legs passed
in every green run, each with the 1,388 tests a run in one process collects.

Not every run was green.
In attempt 2 of run 44033895259, one worker of `test (3.12)` ended, which under xdist is
what a test that runs out of time does, and the job then hung for 30 minutes until it
was cancelled.
No trace named the test, because the timeout’s stack dump is lost with the
worker’s output. `tests/suite_workers.py` now writes every stack to the log before each
test’s budget ends, and bead `mb-pc9v` tracks the hang.

### Phase 2: Split Jobs in the Workflow

Expected: a pull request wall clock of 4 to 5 minutes (est.), or about 3 with the unit
jobs split in two. The owner approved these workflow changes on 2026-11-16 (Q1).

- [x] `mb-oz36`: Split `ci.yml` into `unit`, `goldens`, and `chrome` jobs, with the
  serial tier in `goldens` on every interpreter, and the Chrome tier on one interpreter
  for a pull request and on all four for `main` and while `main` is red.
  It also turns `fail-fast` off, cancels superseded pull request runs, and adds time
  limits, `ci-ok`, and the merge procedure in `AGENTS.md`.
- [x] `mb-to1c`: Add `devtools/check_ci.py` to `make lint-check`.
- [x] `mb-r283`: Run `stack-integration` by tree identity, as split jobs.
- [x] `mb-stg2`: Add the nightly workflow: the serial and Chrome tiers five times on
  `main`, and the time-limit report.
- [ ] `mb-ohsk`: Verify Phase 2 after the merge: the rows of
  [Testing Strategy](#testing-strategy) that need a merged workflow, and each new job’s
  limit again, from more runs than the two that set it.

#### Phase 2 Measurements

Taken on 2026-11-17 from the first CI runs of jlevy/metabrowser#504: 44037230262 at
`3c1502d1`, and 44038762653 at `6dfc1ae5`, which went green.
Other pull requests’ runs, on the workflow before this one, held most of the account’s
runners throughout, so each job’s wait for a runner is given apart from its running
time.

| Job | Jobs | Running, minutes | Waiting for a runner, minutes |
| --- | ---: | ---: | ---: |
| `plan` | 1 | 0.1 | 10.9 |
| `unit` | 8 | 1.9 to 3.7 | 1.9 to 10.5 |
| `goldens and serial` | 4 | 2.9 to 4.1 | 9.3 to 10.6 |
| `chrome` | 4 | 1.9 to 3.9 | 0.8 to 4.8 |
| `admitted-git` | 2 | 3.6 to 3.9 | 3.2 to 8.9 |
| `lint` | 1 | 1.5 | 1.6 |
| `distribution` | 1 | 0.8 | 7.3 |
| `ci-ok` | 1 | 0.1 | 0.1 |

- **The critical path is 4.2 minutes of running time:** `goldens and serial (3.14t)`,
  4.1, whose goldens took 143 seconds where the other interpreters’ took 85 to 96, then
  `ci-ok`. `plan` and the slowest Chrome part come to 4.0, and the slowest `unit` part
  to 3.7.
- **Push to verdict was 19.4 minutes**, almost all of it the wait for runners.
  The run used 56.6 runner minutes, against `main`’s median of 99.5
  ([Phase 1 Measurements](#phase-1-measurements)).
- **The unit parts deal whole files** (`--shard-by=file`, `tests/suite_tiers.py`). Dealt
  by test, run 44037230262 failed every `unit` leg on two tests that rely on an earlier
  test in their module, `test_cli_git_pin_golden.py` and `test_github_pulls.py`; one leg
  also hung after an xdist worker went down and was stopped by its limit.
  By file, the part with the larger files is the slower one: 2.6 to 3.3 minutes of
  pytest against 1.5 to 2.2.
- **Every test ran once.** On each interpreter the two `unit` parts held 3,353 and 3,352
  tests and the serial tier 35, and the Chrome parts held 41 on 3.13: 6,781, the whole
  collection at that commit.
- **A formal GitHub stack already tests against `main`.** Once #504 was linked into a
  stack with #499, GitHub’s merge ref for it merged the head into its base merged with
  `main`, so the `plan` job found the trees identical and ran no `stack-integration`
  job. Run 44037230262, made before the stack was linked, tested the head merged into its
  base alone, found the trees different, and ran all eight; seven passed, and the eighth
  failed on the two tests above.
- **A cancelled run still runs its `ci-ok`**, which is `always()`, and the newer run
  starts only after it: run 44038762653 waited 1.1 minutes so.
- **The third run, 44041984874 at `e3851c64`, went green in 11.2 minutes** from its
  push, with waits for a runner of up to 5.3. Its 30 jobs ran 0.1 to 4.7 minutes, the
  longest `unit (3.14t, 2/2)`; its critical path was that part and `ci-ok`, 4.8 minutes
  of running time. It ran the eight `stack-integration` jobs, since #499 had moved on
  past the commit #504 was built on, and they ran 1.2 to 4.2 minutes each.
- **With runners free, push to verdict was 4.7 minutes.** Run 44043888346, at
  `e6f77bfb`, waited 0.1 minutes at most for a runner.
  Its critical path was `plan`, the slowest Chrome part (4.3), and `ci-ok`; the slowest
  `unit` part took 4.2. It used 57.0 runner minutes.
  One `unit` leg failed, on a race in `test_cli_github_pull_files_golden.py` that the
  module shows whole and in order too (`mb-kq72`).

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
| A test that fails only under xdist | The same 10 runs | Fixed, or marked `serial` with the failure as the marker’s reason, which keeps it on every interpreter. A module in `ADMITTED_GIT_TESTS` is fixed, not marked |
| `make test-admitted-git` under xdist | The pull request’s `admitted-git` jobs over the same 10 runs | Both Git legs green in all 10, with the test count of a serial run of `ADMITTED_GIT_TESTS` on the same commit |
| Concurrent goldens | 10 runs | The 453 commands pass, and each file’s verdict equals a run with `GOLDEN_JOBS=1` |
| The `gh` guard’s summary | A test that makes a guarded `gh` call in a worker | The summary names it |
| Split jobs | 20 pull request runs after the merge | Median push to green at or under 5 minutes, 90th percentile at or under 6, and `unit`, the serial tier, and `chrome` together collecting the tests today’s `test` job collects on the same commit |
| `ci-ok` | A pull request with one deliberately failing shard, closed unmerged | `ci-ok` is red and names it; the other jobs finish |
| `main`’s state | `devtools/ci_plan.sh`’s tests over recorded API answers: success, failure, cancelled, timed out, no run, a failed read, and the unfinished runs in the table below | Only `success` keeps the Chrome tier on `PR_CHROME_PYTHON` (narrow); every other completed answer gives it all of `PYTHONS` |
| Whether a run tested the red head | `ci_plan.sh`’s tests with a merge commit that contains the red head, one that predates it, and a red head the clone lacks | `tests-red` is `yes` for the first only; the summary gives “predates” for the second and a missing commit, with a warning, for the third |
| The verdict line | `ci_verdict.sh`’s tests | While `main` is red, the line has the fixed format, in the log and as a `::notice::`; while it is green, there is no line |
| A red `main` in CI | The first pull request run after `main` is next red, and a rerun of a run from before | Both have the Chrome tier on all four; the first’s verdict line says `tested=yes` with `main`’s head, and the rerun’s says `tested=no` |
| Cancellation | Two pushes a minute apart | The first run is cancelled; a `main` run is never cancelled |
| `stack-integration` | A formal stack, an informal chain behind `main`, one level with it, and one that conflicts; and a formal stack planned after `main` moved | `contained`, `needed`, `identical`, and `conflict`, each with its summary; and `needed` with no `main` state read |
| Nightly soak | One manual run by `workflow_dispatch` | 5 serial-tier jobs and 20 Chrome shard jobs run and report |
| Flake fixes | The loaded-machine loop that `mb-alff` and `mb-nvo0` used | The failure reproduces before the fix and not in 30 runs after it |
| The whole plan | The research brief’s tables, taken again 7 days after Phase 2 | The goals above |

The unfinished runs in `ci_plan.sh`’s tests, each followed by the run behind it, and the
result the state rule gives:

| Recorded answer | Result |
| --- | --- |
| A first attempt in progress, then `success` | Green, narrow |
| A first attempt in progress, then `failure` | Red; `main-run-sha` is the failed run’s head |
| Two first attempts in progress, then `success` | Green, narrow |
| A queued run, then `success` | Green, narrow |
| A rerun in progress whose earlier attempt failed, then `success` | Red; `main-run-sha` is the rerun’s head |
| No completed attempt in the page | Red |

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

- **The xdist factor is under 2.3.** Phase 1 measured 2.0 to 2.2 on four workers
  ([Phase 1 Measurements](#phase-1-measurements)), so the `unit` jobs are split in two,
  which costs four more jobs and no coverage.
- **Tests that are sensitive to load.** A test that passes alone and fails beside three
  workers is found by the 10-run step, and fixed or marked `serial`, which keeps it on
  every interpreter. Two modules outside the Chrome tier, `test_cli_main.py` and
  `test_refresh_signals.py`, probe for a free port and then bind it, which two workers
  can race. `test_refresh_signals.py` is in `ADMITTED_GIT_TESTS`, which runs under xdist
  with no marker filter and whose gate refuses `serial`, so it has to be fixed, not
  marked.
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
  `main`. The merging agent sees it when that run ends, and until `main` is green, a
  pull request merges only by passing `main`’s whole matrix on a tree that contains the
  failure.
- **Merges wait for `main`.** The agent merges only when the latest attempt of `main`’s
  newest run has completed, so merges are spaced by a `main` run, about 5 minutes
  (est.), and a stack lands one layer a run.
  That is accepted: without it, a pull request checked on one interpreter could land on
  a `main` nobody has verified.
- **A red `main` costs every pull request.** While `main` is red, each pull request run
  is 30 jobs, not 18, and draws the Chrome tier four times.
  A red `main` from a flake is therefore rerun when the merging agent sees it.
- **A `ci-ok` that went green before `main` turned red** still reads green.
  The merge procedure covers it for agents.
  A merge by hand, or by auto-merge the owner arms, is not covered, unless the owner
  requires up-to-date branches (Q5).
- **Growth continues.** The Chrome tier went from nothing to 6.3 minutes in five days.
  The shard count and the time limits are how the design absorbs that.
- **A developer machine under xdist** runs one worker per processor, which is heavy
  where several agents share a machine; `PYTEST_WORKERS` lowers it.

### The Pull-Request Path

*Added 2026-11-22 (bead `mb-j5j2`).* A pull request’s run took 7.0 minutes (run
45063672769), and the owner gave three directions that day, which this section carries
out. They supersede [Jobs](#jobs) and the pull-request column of
[How Coverage Is Kept](#how-coverage-is-kept) for a pull request while `main` is green,
and they decide [Path Classes](#path-classes) for the Chrome tier.

> We should aim to have a much faster routine CI cycle.
> 6 minutes is too long.
> It should be, ideally, more like 3. unless There’s a really strong reason that that’s
> difficult.

> can you be sure these longer-lived tests are only run occasionally, not blocking CI on
> a routine basis?

> we should not be paying Chrome testing costs on CI in terms of time if all we’re
> changing is the CLI or backend things that may not need Chrome testing.

The `plan` job now decides a **path** for the whole run, where before it decided only
the Chrome tier’s interpreters:

|  | Main path | Pull-request path |
| --- | --- | --- |
| When | a push to `main`; a pull request while `main` is red | a pull request while `main` is green |
| Interpreters, every tier | `PYTHONS` | `PR_CHROME_PYTHON` |
| Chrome tier | whole (`make test-chrome`) | whole, and only when the change touches a browser path; until 2026-11-25, without its slow tests |
| `admitted-git` | every admitted release | the lowest, which is the security floor |
| Parts | fewer, longer | more, shorter, on the one interpreter |

- **Slow Chrome tests** were those measured at 20 seconds or more in
  `devtools/shard_weights.json`. The owner chose that they run on every push to `main`,
  in the nightly soak, and in the release gate (`make test`, `make verify`), and not on
  a pull request, which passed `--skip-slow`.

  *2026-11-25: withdrawn.* In one week three pull requests (#835, #855, and #858) merged
  green and broke a slow Chrome test on `main`, and each red `main` held every other
  merge until its fix landed; the owner’s direction was “We need to be able to make
  faster progress.” A pull request that touches a browser path now runs the whole tier,
  in more parts so that its longest job is about what it was (`CHROME_SHARDS_PR` in
  `devtools/ci_plan.sh`, with the measurement), and `--skip-slow` and
  `make test-chrome-fast` are gone, so no run can hold part of the tier.
  Choosing slow tests by the files a change touches was rejected: #858 renumbered keys
  in the shell’s scripts and broke a test of the Files tab, which no map by module would
  have named. Bead `mb-593d` has the three failures.

- **Browser paths** are `BROWSER_PATHS` in `devtools/ci_plan.sh`, each with its reason:
  what the browser loads, the Python that builds the shell page and what it writes into
  it, the Chrome tests and the support they share, and what decides and runs the tier.
  A pull request that touches none of them runs no Chrome job, and `ci-ok` accepts that
  skip only on the `plan` job’s `chrome=none`. A backend change can still break a Chrome
  test, because each drives a real server.
  The net is the one [The browser tier’s interpreters](#decisions-and-open-questions)
  already relies on: every push to `main` runs the whole tier on every interpreter, and
  while `main` is red every pull request does.

- **One interpreter** for the unit, goldens, and serial tiers follows the precedent of
  decision 3 for the Chrome tier, and for the same reason.
  A break only another interpreter shows is found on `main`, as a Chrome one was.

- **The parts** each path deals a tier into are constants in `devtools/ci_plan.sh`,
  beside the measurements that set them.

`devtools/check_ci.py` holds every tier’s interpreters, parts, and Gits to the `plan`
job’s outputs and the Chrome job to the whole tier and the plan’s condition, and
`tests/test_ci_plan.py` holds that the main path narrows nothing: all of `PYTHONS`,
every part, the whole Chrome tier, and every admitted Git.

**What it reaches, and what three minutes needs.** A run’s wall clock is about 30
seconds to start, 10 for the `plan` job the tiers now wait for, its slowest job, and 10
of `ci-ok`. On the pull-request path’s first run (45069289704, with `unit` in three
parts):

| Job | Seconds, each part | Was, per job (run 45063672769) |
| --- | --- | --- |
| `unit` | 150 to 189 | up to 316 |
| `goldens and serial` | 115 to 133 | up to 279 |
| `chrome`, without the slow tests | 148 to 160; none when no browser path changed | up to 372 |
| `admitted-git`, lowest release | 146 and 163 | up to 250 |
| `lint` | 136 | the same |

That is about four minutes where it was seven, when no job waits for a runner.
A job spends 45 to 60 seconds before its first test: 16 to 30 on checkout and setup,
then `make install` and pytest’s collection of the whole suite, which each pytest job
repeats.
Two things keep the slowest job above the 130 seconds that three minutes leaves:

- One file, `tests/test_github_pulls.py`, takes about 112 seconds on its worker, in both
  the `unit` and `admitted-git` jobs, and a file runs on one worker, in order.
  No number of parts brings its part under about 175 seconds; splitting the file would
  bring `unit` to about 140.
- Collection costs each pytest job 27 to 40 seconds.
  Passing a part only its own files would need the plan to know every file a tier’s
  tests live in before collecting, which only collection says; it is not done here.

`make ci-report` gives the times the path reaches as they change.

## Decisions and Open Questions

The owner answered four of the questions on 2026-11-16, the answers relayed on
2026-11-17 decide a fifth, and the owner decided a sixth on 2026-11-17.

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
   change. It stops a pull request with a red `ci.yml` run from merging.
   `macos-app.yml` is a separate, path-filtered workflow outside `ci-ok`, so a red macOS
   job still does not block a merge.
   The required check names GitHub Actions as its expected source, so no other app’s
   status named `ci-ok` satisfies it.
   An option for the owner, not the default: the ruleset can also require a branch to be
   up to date with `main` before it merges.
   Every merge then tests the tree that lands, which closes the gaps of
   [A Red `main`](#a-red-main) for merges by hand too, at the cost of one more pull
   request run, 18 jobs (est.), for each pull request that waits behind another merge.
5. **A red `main` (Q6), 2026-11-17.** While `main` is red, a pull request runs `main`’s
   whole matrix, and the merging agent merges only by the rules of
   [A Red `main`](#a-red-main): once the latest attempt of `main`’s newest run has
   completed, and while it is not green, only a pull request whose `ci-ok` verdict says
   it tested that run’s head.
   Agents never arm auto-merge.
   The `plan` job gets `actions: read`; no job gets `issues: write`. On review A3 of
   #504 the owner extended, on 2026-11-17, the reading of `main`’s state to any pull
   request whose tested commit contains `main`’s head, a formal stack’s layers among
   them, with the stacked rule of the merge procedure in
   [Agent Instructions](../../../../AGENTS.md#git) ([A Red `main`](#a-red-main)).
6. **`stack-integration`’s record (Q4), 2026-11-17: yes.** The owner accepted the `plan`
   job’s summary, with the line in which `ci-ok` says why it accepted the skip, as the
   record of a skipped integration, in place of step gating, on review A8 of #504.

Open, with the plan’s recommendation standing as a proposal:

- **Path classes (Q7).** Are the light runs of Phase 3 wanted, for 16 percent of pull
  requests?
- **A merge queue (Q8)** is not proposed.
  Whether a repository owned by a user account can enable one was not established, and
  with the matrix at about five minutes little is left for it to move.
- **A red nightly soak (Q9).** Who reads it?
  A red nightly does not make `main` red, since the `plan` job reads only `ci.yml` runs.
  The proposal: the merging agent reads the newest nightly run when it starts merging,
  and gives each failure it names a bead.

## References

- [Why CI Takes Twenty Minutes](../../research/research-2026-11-16-ci-speed.md): the
  measurements, the options, and what was not measured
- [End-to-End Testing](../../../e2e-testing.md): the tiers, skips, timeouts, and
  `make test-report`
- [Supply-Chain Security](../../../../SUPPLY-CHAIN-SECURITY.md): the rules for a
  dependency or an action; Phase 2 adds the record of the `plan` job’s permission
- [Agent Instructions](../../../../AGENTS.md): bounds are set from measurements, and a
  check is preferred to a sentence; Phase 2 adds the merge procedure to its Git section
- [Development](../../../development.md#documentation): a limit is documented beside its
  constant, with the measurement that set it
- Beads `mb-h8zb`, and `mb-alff`, `mb-nvo0`, `mb-551m`, and `mb-zv5s` for the flakes
  already traced

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
