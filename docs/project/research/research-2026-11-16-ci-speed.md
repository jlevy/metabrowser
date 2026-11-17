# Research: Why CI Takes Twenty Minutes

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete.
Bead `mb-h8zb` tracks it.
The [fast CI plan](../specs/active/plan-2026-11-16-fast-ci.md) acts on it.
Every number is measured from GitHub Actions run data unless it is marked as an
estimate; [Methodology](#methodology) says how, and
[What Was Not Measured](#what-was-not-measured) lists the estimates.

## Overview

The owner asked, on 2026-11-16:

> “I need you to delegate to another sub-agent to investigate why CI is taking so long.
> This is unacceptably slow for CI. CI should be something like 3 to 5 minutes, or else
> we should figure out ways to avoid extraneous checks except when they’re appropriate.
> Delegate to a Fable sub-agent to properly assess this end-to-end and what the proper
> engineering solution is to maintain the same levels of coverage but speed up our
> development velocity.”

A push to a pull request waits a median of 20.5 minutes for a green CI run, and 24.4
minutes at the 90th percentile.
CI was inside the owner’s target until late September: a green run on `main` took 3.1
minutes in the week of 2026-09-14 and takes 22.4 minutes in the week of 2026-11-16.

Three things account for the time, in this order:

1. The test suite runs in one process on a runner that has four processors, so three of
   them idle while each of four or five jobs runs the whole suite end to end.
2. A headless Chrome tier that did not exist before 2026-11-12 now takes 6.3 minutes of
   every such job, and it is where 30 of the 31 proven flaky job failures were.
3. A flake in one job cancels its sibling jobs and costs a full rerun, so a run that
   needed a rerun reached green a median of 102 minutes after its push.

Setup, installation, and caching are not a cause: they take about 20 seconds of each
job.

## Questions to Answer

1. Where do the minutes of a CI run go, by job, step, and test?
2. How much of that is headless Chrome, and how much is serial work that could run in
   parallel?
3. How often does a run fail on a flake, and what does that cost?
4. Which techniques would bring the pull request loop to 3 to 5 minutes, and what does
   each risk in coverage?

## Scope

Included: `.github/workflows/ci.yml` and what it calls (the `Makefile` targets
`lint-check`, `audit`, `test`, `test-admitted-git`, and `build`), `lefthook.yml`, the
pytest configuration, `tests/conftest.py`, the tryscript goldens, and the rules in
[Supply-Chain Security](../../../SUPPLY-CHAIN-SECURITY.md) that govern any new tool.
`macos-app.yml` is measured only for its wall clock.

Excluded: `publish.yml`, the outer test tiers that no CI job runs
([Test Tiers](../../e2e-testing.md#test-tiers)), and the speed of the product itself.

This brief changes no workflow, Makefile target, dependency, or repository setting.

## Findings

### The Pipeline Today

Every push to a pull request, and every push to `main`, runs nine jobs on
`ubuntu-latest`:

| Job | What it runs | Runs on |
| --- | --- | --- |
| `lint` | `make lint-check audit` | Python 3.13 |
| `distribution` | `make build` | Python 3.13 |
| `test` | `make test`: pytest over the whole suite, then the tryscript goldens | Python 3.12, 3.13, 3.14, and 3.14t |
| `admitted-git` | `make test-admitted-git`: the `ADMITTED_GIT_TESTS` modules on a Git built from source | Git 2.43.7 and 2.50.1, Python 3.13 |
| `stack-integration` | `make lint-check test` on the pull request’s head merged with `main` | Python 3.13, and only when the base is not `main` |

`macos-app.yml` adds a macOS job when a change touches `apps/macos/**`, the `Makefile`,
or that workflow. Its median is 5.0 minutes and its 90th percentile 6.0, over 56 green
runs.

The `test` matrix leaves `fail-fast` at its default, so the first leg to fail cancels
the other three. `ci.yml` has no `concurrency` group, so a run that a newer push has
superseded runs to the end.
The repository has no branch protection and no ruleset, so no check is required before a
merge.

### Where a Run’s Minutes Go

The sample is the last 300 runs of `ci.yml`, created from 2026-11-14 08:57 to 2026-11-17
01:14 UTC: 259 on pull requests and 41 on `main`, 322 run attempts and 2,898 job
records.

Wall clock from the push to the last job’s end, for first attempts:

| Run | Outcome | Runs | Median (min) | 90th percentile (min) | Median runner minutes |
| --- | --- | ---: | ---: | ---: | ---: |
| Pull request to `main` | green | 96 | 20.5 | 24.4 | 84.1 |
| Stacked pull request | green | 77 | 21.1 | 23.5 | 107.2 |
| Push to `main` | green | 36 | 20.6 | 23.5 | 84.9 |
| Pull request to `main` | red | 33 | 16.8 | 19.8 | 78.9 |
| Stacked pull request | red | 48 | 17.5 | 23.0 | 89.1 |

A red run’s first failed job ended a median of 11.2 minutes after the push for a pull
request to `main`, and 14.6 minutes for a stacked one.

Durations of successful jobs:

| Job | Jobs | Median (min) | 90th percentile (min) | Longest (min) |
| --- | ---: | ---: | ---: | ---: |
| `lint` | 317 | 1.5 | 1.7 | 2.4 |
| `distribution` | 322 | 0.7 | 0.8 | 5.9 |
| `admitted-git (2.43.7)` | 317 | 6.4 | 7.0 | 8.6 |
| `admitted-git (2.50.1)` | 317 | 6.5 | 7.0 | 10.3 |
| `test (3.12)` | 241 | 17.9 | 20.8 | 23.3 |
| `test (3.13)` | 236 | 17.4 | 20.5 | 22.9 |
| `test (3.14)` | 239 | 18.0 | 21.4 | 23.6 |
| `test (3.14t)` | 233 | 20.2 | 23.6 | 26.9 |
| `stack-integration`, stacked | 107 | 19.4 | 21.6 | 22.8 |
| `stack-integration`, base is `main` | 166 | 0.1 | 0.1 | 0.1 |

Steps of those jobs.
The setup steps are the same in every job, to within 0.02 minutes:

| Step | Median (min) | 90th percentile (min) |
| --- | ---: | ---: |
| Checkout, full history | 0.08 | 0.12 |
| Install uv, cache restored | 0.03 | 0.05 |
| Set up Node, cache restored | 0.10 | 0.12 |
| Set up Python | under 0.05 | under 0.05 |
| Restore the admitted Git build | 0.03 | 0.05 |
| `lint`: `make lint-check audit` | 1.13 | 1.41 |
| `distribution`: `make build` | 0.40 | 0.48 |
| `admitted-git`: `make test-admitted-git` | 6.0 to 6.1 | 6.7 |
| `test`: `make test` | 17.1 to 19.9 | 20.1 to 23.2 |
| `stack-integration`: `make lint-check test` | 19.0 | 21.2 |

Inside the `make` step, read from the logs of 18 green runs (8 on `main` and 10 on pull
requests), in seconds:

| Job | `make install` | pytest | tryscript goldens |
| --- | ---: | ---: | ---: |
| `test (3.12)` | 4.5 | 926 (p90 1,059) | 204 (p90 264) |
| `test (3.13)` | 4.3 | 857 (p90 1,015) | 197 (p90 243) |
| `test (3.14)` | 5.4 | 954 (p90 1,054) | 251 (p90 275) |
| `test (3.14t)` | 4.8 | 965 (p90 1,144) | 258 (p90 298) |
| `admitted-git (2.50.1)` | 4.3 | 358 (p90 402) | not run |
| `lint` | 4.0 | not run | not run |

`make install` is `uv sync --locked` and `npm ci` on restored caches.
The `lint` job spends a median of 57 seconds in `make lint-check` (p90 80) and under a
second in `make audit`. In run 43990430371 its largest parts were BasedPyright at 22
seconds, `devtools.check_parity` at 14, `devtools.public_hygiene` at 8, and the three
`tsc` passes at 7.

So in a `test` leg, setup and installation take about 20 seconds, pytest takes 14 to 16
minutes, and the goldens take 3.3 to 4.3 minutes.

### Where the Test Suite’s Minutes Go

`test (3.13)` of run 43990430371 collected 6,507 passing tests in 387 modules and ran
them in 886 seconds, then ran 453 tryscript commands in 80 goldens in 204 seconds.
Per-module time is read from the log by `make test-report`
([Measuring the Suite](../../e2e-testing.md#measuring-the-suite)).

The time is concentrated: the five slowest modules take 36 percent of pytest, the
slowest 20 take 65 percent, and the slowest 50 take 80 percent.

Twenty modules launch headless Chrome through the `chrome_profile` fixture.
They are the **Chrome tier** below; one of them, `tests/test_process_group.py`, is
mostly timing checks of the process-group helper.
Over the 18 runs, in seconds:

| Leg | Chrome tier | Every other module | Goldens |
| --- | ---: | ---: | ---: |
| `test (3.12)` | 382 (p90 396) | 563 (p90 652) | 205 (p90 265) |
| `test (3.13)` | 373 (p90 396) | 510 (p90 608) | 197 (p90 243) |
| `test (3.14)` | 381 (p90 399) | 601 (p90 639) | 251 (p90 275) |
| `test (3.14t)` | 382 (p90 397) | 661 (p90 733) | 258 (p90 299) |

The Chrome tier takes the same 6.3 minutes on every Python version, which is what a tier
bounded by the browser’s clock and not by the interpreter would show.
It is 35 to 39 percent of pytest’s time and about a third of a `test` leg.
The other modules vary by interpreter, and for one commit they vary from run to run: the
five `main` runs at 6,507 tests took 446 to 647 seconds for them.

The slowest modules in `test (3.13)`, median of 18 runs:

| Module | Seconds | Tier |
| --- | ---: | --- |
| `tests/test_transitions_instrument.py` | 123.9 | Chrome |
| `tests/test_process_group.py` | 57.2 | Chrome |
| `tests/test_github_pulls.py` | 55.9 | other |
| `tests/test_checkout_overlay.py` | 42.6 | other |
| `tests/test_github_pull_header_chrome.py` | 39.5 | Chrome |
| `tests/test_files_tab_chrome.py` | 38.0 | Chrome |
| `tests/test_raw_profile_cache_chrome.py` | 28.0 | Chrome |
| `tests/test_github_checkout.py` | 28.0 | other |
| `tests/test_refresh_signals.py` | 26.0 | other |
| `tests/test_changed_file_rows_chrome.py` | 25.4 | Chrome |
| `tests/test_github_pulls_stacks_chrome.py` | 16.0 | Chrome |
| `tests/test_folder_home_chrome.py` | 15.1 | Chrome |
| `tests/test_check_parity.py` | 14.3 | other |
| `tests/test_cache_update.py` | 13.4 | other |
| `tests/test_plugin_public_api.py` | 11.1 | other |

The slowest single tests, from `--durations=25` of the same job:

| Test | Seconds |
| --- | ---: |
| `test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome` | 38.1 |
| `test_transitions_instrument.py::test_transition_recorder_in_chrome[landing-11]` | 28.4 |
| `test_raw_profile_cache_chrome.py::test_a_trusted_answer_kept_by_chrome_runs_nothing_after_untrusted` | 28.0 |
| `test_changed_file_rows_chrome.py::test_the_diff_summary_opens_in_the_pages_flow_on_the_trees_step` | 22.2 |
| `test_transitions_instrument.py::test_transition_recorder_in_chrome[content-10]` | 19.7 |
| `test_transitions_instrument.py::test_transition_recorder_in_chrome[search-19]` | 18.3 |
| `test_transitions_instrument.py::test_transition_recorder_in_chrome[readings-4]` | 18.0 |
| `test_github_pulls_stacks_chrome.py::test_the_pulls_stack_groups_share_the_stack_menus_design_in_chrome` | 16.1 |
| `test_folder_home_chrome.py::test_the_folder_name_and_zero_go_home_as_a_fresh_load_shows_it` | 14.9 |
| `test_check_parity.py::test_the_real_table_passes` | 13.3 |
| `test_process_group.py::test_a_stop_keeps_to_its_reserved_time_with_a_pipe_held_outside_the_group` | 12.5 |
| `test_github_pull_header_chrome.py::test_the_pull_header_keeps_its_box_in_chrome`, each of three cases | 10.2 |

Twenty-three of the 25 slowest tests are in the Chrome tier.
The three pull-header cases take 10.24, 10.25, and 10.26 seconds, which suggests a fixed
wait and not work.

The goldens average 0.43 seconds a command on Python 3.13 and 0.57 on 3.14t, since each
command starts `metab` in a new process.
The slowest are `cli-github-pull.tryscript.md` at 26 seconds,
`cli-github-pull-files.tryscript.md` at 18, and `cli-api-source.tryscript.md` at 14.
tryscript 0.3.1 runs its files one after another and has no option to run them
concurrently.

The `admitted-git` job’s 59 modules take a median of 340 seconds, and four of them take
half of it: `test_github_pulls.py` at 64, `test_checkout_overlay.py` at 49,
`test_github_checkout.py` at 30, and `test_refresh_signals.py` at 27. None is in the
Chrome tier.

### What Runs More Than Once

One push runs the same test content this many times:

| Content | Pull request to `main` | Stacked pull request |
| --- | ---: | ---: |
| The whole pytest suite | 4 | 5 |
| The Chrome tier | 4 | 5 |
| The tryscript goldens | 4 | 5 |
| The `ADMITTED_GIT_TESTS` modules | 6 | 7 |
| `make lint-check` | 1 | 2 |

Each repetition on another interpreter or another Git has a reason, and history shows
the interpreter legs earn it: commit `3d943444f` removed a use of an argument that
`Path.is_dir` has only from Python 3.13, and commit `8af9d8e3f` hardened the
free-threaded runtime.
The Chrome tier is the exception.
It measures layout, paint, and input in the browser against a server whose bytes the
route tests and goldens pin on every interpreter, and its time does not change with the
interpreter.

### The Suite Is Growing Quickly

Median wall clock of green runs on `main`, by week:

| Week of | Pushes to `main` | Median (min) |
| --- | ---: | ---: |
| 2026-08-10 | 22 | 1.3 |
| 2026-09-14 | 23 | 3.1 |
| 2026-10-26 | 6 | 8.6 |
| 2026-11-02 | 12 | 12.7 |
| 2026-11-09 | 73 | 18.0 |
| 2026-11-16 | 19 | 22.4 |

Within the 64 hours of the sample, the `test (3.13)` job went from 5,922 tests in 352
modules to 6,507 in 387, and the Chrome tier went from 197 seconds to about 380. The
first Chrome module was written on 2026-11-12, and 20 are on `main` five days later.
The goldens went from 40 files on 2026-11-01 to 80.

Nothing bounds this.
A test’s cost is paid in series, four or five times a push, and no check reports when a
job’s time passes a limit.

### Flakes and What They Cost

Of the 322 run attempts, 92 failed.
Each is classed by evidence from the same commit:

| Class | Attempts | Evidence |
| --- | ---: | --- |
| Proven flake | 30 | For 22, a rerun of the same commit went green with no change. For 8, another job that ran the same suite on the same commit passed |
| Real failure | 29 | 25 where two or more independent jobs failed the same modules, 3 lint failures, and 1 conflict with `main` |
| Undetermined | 33 | One job failed and `fail-fast` cancelled the others, so nothing says whether they would have passed |

So at least 9.3 percent of all run attempts, and a third of the failed ones, failed on a
flake.
The undetermined class includes all four red runs on `main`, each with one failing
module in one leg.

Where the proven flakes were:

- Of the 31 failed jobs in those 30 attempts, 30 were in a Chrome-tier module.
- `tests/test_files_tab_chrome.py` was in 22 of the 30 attempts.
  `mb-alff` traced it to the product: a focus restore cancelled a pending tooltip.
  jlevy/metabrowser#481 fixed that on 2026-11-16 23:15 UTC. The module failed 31 of
  1,067 completed full-suite jobs before the fix and 0 of 109 after it.
- The rest: `test_transitions_instrument.py` in 3, `test_prose_faces_chrome.py` in 2
  (`mb-nvo0`, fixed by jlevy/metabrowser#488), `test_changed_file_rows_chrome.py` in 2
  (“Chrome wrote no DevTools port” from `tests/dom/chrome-session.mjs`),
  `test_github_pulls_stacks_chrome.py` in 1, `test_nav_metadata_chrome.py` in 1, and
  `test_github_pulls.py` in 1 (`gh did not answer within 15 s`).
- `mb-551m` (`test_nav_reveal_chrome.py`) and `mb-zv5s` (a Chrome session that outlives
  its result) are open.

What they cost:

- **Exposure multiplies.** A completed full-suite job failed on a proven flake 2.6
  percent of the time (31 of 1,176). With four such jobs a push, that is a 10 percent
  chance that a run fails with nothing wrong, and 12.5 percent with five.
- **A flake costs a full rerun.** The 22 reruns re-executed 65 `test` legs and 5
  `stack-integration` jobs for 22 single failing tests, because the cancelled legs have
  to run again too. Each rerun took a median of 20.5 minutes, and together they took 440
  minutes of wall clock and 1,292 runner minutes.
- **The wait is longer than the rerun.** The 15 runs that needed a rerun reached green a
  median of 102 minutes after their push, and between 39 and 562, against 20.5 minutes
  for a run that needed none.
  Two of them needed two reruns, one needed three, and one needed four.
- **The evidence is thrown away.** `fail-fast` saves runner minutes on a real failure,
  and in 33 attempts it also removed the only way to tell a flake from a real failure
  without a rerun.

### Superseded Runs, Stacks, and What Changed

- **Superseded runs.** A newer push to the same branch arrived before the run finished
  for 44 of the 259 pull request runs, 17 percent.
  Those runs spent 1,543 runner minutes after the push that made their result moot.
- **Stacks.** Of the pull request runs with a result, 125 of 254 were on a stacked pull
  request, and 50 of the last 150 merged pull requests had a base other than `main`. A
  stacked run costs a median of 107 runner minutes.
  In 33 of 69 sampled stacked runs, the `stack-integration` merge step printed
  `Already up to date.`: `main` was already in the pull request’s head, so the job ran
  the whole gate on the head’s own tree.
- **What a pull request changes.** Of the last 150 merged pull requests, 13 changed only
  documentation, 11 changed only `apps/macos/` and documentation, and 10 changed no
  Python or build input.
  The other 116, 77 percent, changed Python sources, Python tests, `devtools/`, or build
  inputs. All 150 ran the same nine jobs.

### Runner Capacity and Queueing

The sample used about 28,000 runner minutes in 64 hours: 26,957 in first attempts and
1,292 in reruns. The repository ran 142 CI runs on 2026-11-16.

A standard GitHub-hosted Linux runner for a public repository has 4 processors and 16 GB
of memory ([GitHub-hosted runners](#references)). pytest runs in one process and
tryscript runs one command at a time, so a `test` leg uses about one of the four.

Up to 65 jobs of this workflow ran at once, and 20 or more ran for 10.1 of the 64.3
hours. A job waited a median of 2 seconds for a runner, 1.5 minutes at the 90th
percentile, and up to 8.8 minutes; 12 percent of jobs waited more than a minute.

## Key Insights

- **The runner’s other three processors are the largest unused resource.** The fix with
  the best ratio of payoff to risk is to use them, not to run fewer checks.
- **Caching is already done.** Setup and installation are 20 seconds of a job, so
  caching uv, npm, Chrome, or the Git builds harder cannot return more than that.
- **The Chrome tier is the long pole and the flake source at once, and it is five days
  old.** It needs a machine to itself, since its flakes reproduce under processor load,
  so it should be split across runners and not run beside other tests.
  It gains nothing from running on four interpreters, and each repetition is another
  draw at a flake.
- **Wall clock is set by the slowest job, and runner minutes by the sum.** Splitting
  work across more, shorter jobs cuts the first; using each runner’s processors cuts the
  second. The repository needs both, since jobs already queue.
- **A flake’s cost is set by the job’s length and by `fail-fast`.** With jobs of a few
  minutes and no cancellation of siblings, a flake costs one short job’s rerun and
  leaves the evidence that it was a flake.
- **Without a limit the time returns.** CI went from 3 minutes to 22 in two months with
  nobody choosing that.
  A limit on each job’s time makes the next slow test a visible decision: add a shard,
  or make the test cheaper.

## Comparison Matrix

The effects are for a pull request to `main` on today’s suite, and an estimate is marked
“est.”

| Technique | Effect on wall clock | Effect on runner minutes | Coverage risk | New dependency or setting |
| --- | --- | --- | --- | --- |
| pytest-xdist in each job, four workers, Chrome tier kept serial | `test` leg from 17 to 20 minutes to about 10 to 12 (est.) | About 35 percent lower (est.) | A test that depends on another test’s process state fails and has to be fixed or marked serial | `pytest-xdist` 3.8.0 and `execnet` 2.1.2, development only |
| Run goldens four files at a time | Goldens from 3.3 to 4.3 minutes to about 1 to 1.4 (est.) | None | None: the same commands run | None |
| Chrome tier in its own jobs, sharded by four | Chrome from 6.3 minutes in a leg to about 2 minutes a shard (est.) | Small rise for setup | None if every test lands in exactly one shard, which a partition gives by construction | None |
| Chrome tier once a push, not once per interpreter | None on its own | About 19 runner minutes lower | Chrome on Python 3.12, 3.14, and 3.14t leaves the pull request; it has to run on `main` | None |
| Separate jobs for unit tests, goldens, and Chrome | Wall clock becomes the slowest of them: about 4 to 5 minutes (est.) | None | None | None |
| `fail-fast: false` | None when green; a flake reruns one job | Higher on a real failure | None; it adds evidence | None |
| Cancel superseded runs | Less queueing | About 5 percent lower (1,543 of 28,000 measured) | None for the latest commit; `main` runs must be exempt | None |
| Skip `stack-integration` when its tree equals the tree the test jobs ran | None | About 20 runner minutes lower in up to 48 percent of stacked runs | None when the trees are identical | None |
| Path classes: documentation-only and macOS-only changes | About 3.5 minutes for those (est.) | 16 percent of pull requests run 4 jobs | A misclassified path skips a check; `main` has to run everything | None |
| Fix the flakes at their root | Removes the 102-minute tail | 1,292 runner minutes in the sample | None | None |
| A time limit on each job | Keeps the gain | None | None | None |
| Merge queue | None | Lower | Changes what gates a merge | Needs branch protection, and possibly an organization |
| Larger runners | Lower | Billed | None | Not offered to this repository’s plan |

## Options Considered

### Parallelism Within a Job

**Description:** Run pytest under pytest-xdist with one worker per processor, and run
tryscript files concurrently.

**Pros:**

- Uses processors the job already has, so it lowers wall clock and runner minutes
  together
- Speeds the local `make test` and the pre-push hook, where machines have more
  processors than a runner
- One reviewed development dependency: `pytest-xdist` 3.8.0, published 2025-07-01, whose
  only requirement beyond pytest is `execnet` 2.1.2, published 2025-11-12. Both are
  MIT-licensed and past the 14-day cool-off

**Cons:**

- Tests share nothing across workers, so a test that relied on another test’s leftovers
  fails. The suite is already built against that: `tests/conftest.py` resets process
  state around every test, and commit `0ea0f6032` ran the suite in reversed module order
  to find the modules that depended on it
- The Chrome tier and the process-group timing tests are sensitive to load and must stay
  serial
- Nine modules probe for a free port and then bind it, which two workers can race.
  Seven are in the Chrome tier; `test_cli_main.py` and `test_refresh_signals.py` are not
- `pytest_terminal_summary` in `tests/conftest.py` reads the `gh` guard’s log from the
  controller’s temporary directory, and under xdist each worker has its own, so the
  guard’s report would be empty until it reads them all
- `devtools/suite_report.py` reads per-module time from the gaps between progress lines,
  which xdist does not print per module

### Sharding Across Jobs

**Description:** Split a tier across several runner jobs, each running a deterministic
part of the collected tests.

**Pros:**

- The only way to speed the Chrome tier, which cannot share a machine
- Scales with the suite: when a tier grows, add a shard
- No dependency: a `--shard` option in `tests/` that deals collected tests into parts

**Cons:**

- Each job pays about 20 seconds of setup
- More jobs at once, where jobs already queue at peak
- By module, the Chrome tier cannot go below the 124 seconds of
  `test_transitions_instrument.py`; three shards by module measure 126 seconds each.
  Dealing by test avoids that floor

### Fewer Repetitions

**Description:** Run the Chrome tier on one interpreter for a pull request, and on all
four for every commit on `main`.

**Pros:**

- Cuts flake exposure from four or five draws a push to one
- Removes about 19 runner minutes a push

**Cons:**

- Chrome on Python 3.12, 3.14, and 3.14t is checked after a merge and not before it

### Path and Impact Selection

**Description:** Classify a pull request by the paths it changes and run fewer jobs for
a class whose changed paths are inputs to fewer checks.

**Pros:**

- A documentation-only or macOS-only pull request, 16 percent of the last 150, needs
  lint, distribution, and the suite once, since no Chrome-tier or `admitted-git` module
  reads repository documentation

**Cons:**

- A wrong path rule skips a check silently, so `main` has to run everything, and the
  rule has to be a check itself
- It does not help the 77 percent of pull requests that change Python or build inputs

### Merge Queue, or Checks on `main`

**Description:** Move expensive checks from every push to the moment of merging, in a
GitHub merge queue, or run them on `main` after the merge.

**Pros:**

- A merge queue tests the exact commit that will land

**Cons:**

- A merge queue needs branch protection with required checks, which this repository does
  not have. GitHub’s documentation, as fetched for this brief, did not state whether a
  repository owned by a user account can enable one
- Once the full matrix fits in about five minutes on a pull request, there is little
  left to move

### Eliminated Options

- **More caching:** Eliminated because setup and installation are 20 seconds of each job
  and every cache already restores.
- **Larger runners:** Eliminated because GitHub offers them to organizations on its Team
  and Enterprise plans and bills them, and the standard runner’s four processors are
  unused today.
- **A test-impact map from imports or coverage:** Eliminated for now because the slowest
  tests depend on JavaScript, CSS, fixtures, and Git, which a Python import graph does
  not see, and a wrong map skips a test silently.
  Path classes take the safe part of the idea.
- **Retrying a failed test automatically:** Eliminated because the dominant flake,
  `mb-alff`, was a product defect that a retry would have hidden.
- **Skipping a job whose tree an earlier run already passed:** Eliminated except within
  one run. A pull request’s cache is not readable from `main` or from another pull
  request, so the record of what passed would need the Checks API, for runs on `main`
  that block nobody.
- **Reverting `main` automatically when it goes red:** Eliminated while a Chrome flake
  can turn `main` red; all four red `main` runs in the sample were one failing module in
  one leg, three of them in the Chrome tier.

## Recommendations

1. Use the runner’s processors: pytest-xdist for every module outside a serial tier, and
   concurrent tryscript files.
2. Give the serial tier, which is the Chrome tier and the process-group timing tests,
   its own sharded jobs on one interpreter for a pull request, and run it on every
   interpreter for every commit on `main`.
3. Split the `test` job into unit, golden, and Chrome jobs, so that the wall clock is
   the slowest of them.
4. Turn `fail-fast` off, cancel superseded pull request runs, and add one job that
   reports the whole run’s verdict.
5. Run `stack-integration` only when merging `main` changes the tree, and as the same
   split jobs.
6. Put a time limit on each job that fails with the instruction to add a shard.
7. Fix the open flakes at their root and soak the Chrome tier on a schedule, away from
   pull requests.
8. Then consider path classes for documentation-only and macOS-only changes.

With 1 through 5, a pull request’s wall clock is estimated at 4 to 5 minutes and its
runner minutes at about 38, against 20.5 and 84 today.
The [fast CI plan](../specs/active/plan-2026-11-16-fast-ci.md) gives the design, the
argument for each check’s coverage, and the order.

## Next Steps

- [x] The owner answered the questions that Phases 1 and 2 of the plan need, on
  2026-11-16
- [ ] Measure the xdist speedup in CI as the first implementation step, since this brief
  could not

## Methodology

- **Runs and jobs.** `gh run list --workflow ci.yml --limit 300` with its JSON fields,
  then `gh api repos/jlevy/metabrowser/actions/runs/<id>/attempts/<n>/jobs` for each of
  the 322 attempts. A job’s duration is `completed_at` minus `started_at`, its queue time
  `started_at` minus `created_at`, and a step’s duration its own two timestamps.
  Percentiles are over successful jobs and interpolate linearly.
- **Phases and modules.** `gh run view <run> --job <job> --log` for every successful job
  of 18 green first-attempt runs: the 8 most recent on `main` and 10 spread across the
  pull request runs. Phase boundaries are the timestamps of the Makefile’s echoed
  commands, pytest’s time is its own summary line, and tryscript’s is its own total.
  Per-module time is `devtools/suite_report.py`’s reading of the same logs.
- **The Chrome tier.** The 20 modules that name `require_chrome`, which are the same 20
  that use the `chrome_profile` fixture, at commit `78bef1634`.
- **Failures.** The log of each of the 144 failed jobs, read for pytest’s failing
  progress lines and section headers, tryscript’s `FAIL` lines, and the merge error.
  A rerun counts as proof of a flake only when it is a later attempt of the same run, so
  of the same commit.
- **Reruns.** A job counts as re-executed in an attempt when its `started_at` differs
  from the same job’s in the attempt before.
- **Stacks.** The `stack-integration` log of every second stacked first attempt, 69 of
  them, read for `Already up to date.`
- **Pull request classes.** `gh pr list --state merged --limit 150 --json files`, each
  path classed by its directory and extension.
- **Trend.** `gh run list --workflow ci.yml --branch main --event push --limit 600`,
  which returned 221 runs back to 2026-07-15; wall clock is `updatedAt` minus
  `startedAt` of green first attempts.
- **Release dates.** The PyPI JSON API for `pytest-xdist` and `execnet`.

### What Was Not Measured

- **The xdist speedup.** The measuring machine was shared and its load average was above
  250, so a local serial-against-parallel pair would have measured the machine.
  A serial run of a quarter of the non-Chrome modules was started and lost to a restart
  at 28 percent. The 2.5 to 3.2 times used in the estimates comes from four processors
  and a suite of independent, process-bound tests; it is an assumption until a CI run
  measures it.
- **Processor use on the runner.** That a `test` leg uses about one processor follows
  from pytest running in one process and tryscript running one command at a time; no run
  sampled it.
- **Which tests fail under xdist.** None was run under it.
  `pytest-xdist` 3.8.0 was only resolved and imported, in a temporary environment, with
  no change to `uv.lock`.
- **Shard balance by test.** The 126 seconds for three shards is measured by module;
  dealing by test is expected to do better and was not simulated.
- **Tree identity for stacks.** `Already up to date.` shows that `main` was in the head.
  That the tree then equals the one the `test` jobs checked out also needs the base
  branch to be in the head, which the logs do not show, so 48 percent is an upper bound.
- **Merge queue availability** for a repository owned by a user account, and the
  account’s concurrent-job limit.
- **No headless Chrome test was run locally.**

## References

- [About GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners):
  official documentation; the 4-processor, 16 GB Linux runner for public repositories,
  and who may use larger runners
- [Actions limits](https://docs.github.com/en/actions/reference/limits): official
  documentation; concurrent jobs by plan, 20 on Free, 40 on Pro, and 60 on Team
- [Managing a merge queue](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue):
  official documentation; the `merge_group` event and the branch protection it needs
- [pytest-xdist on PyPI](https://pypi.org/project/pytest-xdist/) and
  [execnet on PyPI](https://pypi.org/project/execnet/): release dates, requirements, and
  licenses
- [End-to-End Testing](../../e2e-testing.md): the test tiers, skips, and
  `make test-report`
- [Supply-Chain Security](../../../SUPPLY-CHAIN-SECURITY.md): the rules for a new
  dependency or action
- Beads `mb-alff`, `mb-nvo0`, `mb-551m`, and `mb-zv5s`: the Chrome flakes already traced

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
