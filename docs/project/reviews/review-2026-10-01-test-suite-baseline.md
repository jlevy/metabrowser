# Review: Test-Suite Baseline for the v0.12 Test Review

**Date:** 2026-10-01

**Status:** A record of measurements, not a maintained table.
Each figure was taken at the commit and from the CI run named beside it, by the command
shown. For today’s values, run the command.
The commands reproduce these figures only while the commits and CI logs they name exist.
`ea7fd9ba`, `f9cd3e6b`, and `a896d8fe` are tips of stack branches that have not merged,
so a rebase or a deleted branch can remove them, and a CI log is kept only for a time.

**Scope:** The size and run time of the test suite at three commits, as the starting
point of the v0.12 test-suite review, which is tracked by `mb-06up`. This record and the
tool that produced it are `mb-jqbg`.

| Column | Commit | What it is |
| --- | --- | --- |
| main | `6c278f3f` | `origin/main` on the day of the record |
| base | `ea7fd9ba` | `codex/v012-docs-reconcile`, the v0.12 stack before the review’s pull requests |
| tip | `f9cd3e6b` | `codex/v012-tests-golden-machinery`, the stack after the review’s first three |

## How the Numbers Are Taken

`devtools/suite_report.py` reads `tests/` at each commit through Git and reads run times
from a CI job log. [Measuring the Suite](../../e2e-testing.md#measuring-the-suite) says
what each number means.

```shell
# Sizes, and the twelve areas that changed most.
uv --config-file uv.toml run --frozen python -m devtools.suite_report \
  6c278f3f ea7fd9ba f9cd3e6b --areas 12

# Run time: the `test (3.13)` job of the CI run on each commit.
gh run view 35634453594 --job 106448318268 --log > main.log
gh run view 36820018225 --job 110233382508 --log > base.log
gh run view 36844743616 --job 110312072102 --log > tip.log
make test-report REFS=6c278f3f LOG=main.log
make test-report REFS=ea7fd9ba LOG=base.log
make test-report REFS=f9cd3e6b LOG=tip.log
```

## Sizes

| Measure | main | base | tip | Change, main to tip |
| --- | ---: | ---: | ---: | ---: |
| `tests/test_*.py` files | 203 | 276 | 282 | +79 |
| `tests/test_*.py` lines | 49,436 | 79,100 | 79,639 | +30,203 |
| test functions | 1,930 | 2,784 | 2,842 | +912 |
| test helper modules | 3 | 10 | 14 | +11 |
| test helper lines | 323 | 1,967 | 2,864 | +2,541 |
| `tests/dom` files | 84 | 95 | 96 | +12 |
| `tests/dom` lines | 33,638 | 39,573 | 39,496 | +5,858 |
| `tests/golden` files | 24 | 57 | 57 | +33 |
| `tests/golden` lines | 6,058 | 18,853 | 19,416 | +13,358 |
| tryscript commands | 131 | 301 | 306 | +175 |
| `tests/fixtures` files | 32 | 52 | 52 | +20 |
| `tests/fixtures` lines | 972 | 10,249 | 10,249 | +9,277 |
| other files under `tests` | 7 | 8 | 8 | +1 |
| other lines under `tests` | 277 | 287 | 287 | +10 |

The twelve areas of Python tests that changed most from main to the tip, in lines, of
the 73 that changed:

| Area | main | base | tip | Change, main to tip |
| --- | ---: | ---: | ---: | ---: |
| cache | 0 | 7,907 | 7,972 | +7,972 |
| git | 2,409 | 7,944 | 7,909 | +5,500 |
| github | 0 | 3,706 | 3,689 | +3,689 |
| cli | 2,143 | 5,889 | 5,485 | +3,342 |
| source | 150 | 2,904 | 2,797 | +2,647 |
| artifact | 0 | 867 | 867 | +867 |
| plugin | 1,754 | 2,523 | 2,496 | +742 |
| serve | 495 | 1,152 | 1,152 | +657 |
| check | 1,035 | 1,166 | 1,677 | +642 |
| inert | 0 | 583 | 560 | +560 |
| repository | 120 | 572 | 568 | +448 |
| diff | 663 | 1,121 | 1,083 | +420 |

## Run Time

One CI run for each commit, the `test (3.13)` job.

| Measure | main | base | tip |
| --- | ---: | ---: | ---: |
| CI run | 35634453594 | 36820018225 | 36844743616 |
| pytest passed | 2,186 | 3,534 | 3,719 |
| pytest skipped | 0 | 27 | 26 |
| pytest seconds | 64.04 | 265.55 | 255.34 |
| tryscript goldens | 22 | 37 | 37 |
| tryscript seconds | 37.9 | 181.2 | 148.4 |

The base’s run did not pass `-rs`, so its log does not list its 27 skips.
The tip’s log lists its 26 by reason: 15 for ACLs that are inspected only on macOS, 4
for a file system that tells letter case apart, and 7 for the live GitHub tier, which
that run did not select.

The slowest test files and goldens at the tip, in seconds:

| Test file | Seconds | Golden | Seconds |
| --- | ---: | --- | ---: |
| `tests/test_refresh_signals.py` | 29.8 | `cli-cache-url-grammar.tryscript.md` | 26.8 |
| `tests/test_github_pulls.py` | 21.3 | `cli-github-pull.tryscript.md` | 17.8 |
| `tests/test_cache_update.py` | 16.3 | `cli-github-urls.tryscript.md` | 16.6 |
| `tests/test_source_refresh.py` | 8.4 | `cli-api-source.tryscript.md` | 13.0 |
| `tests/test_markdown_mount_js.py` | 8.1 | `cli-show.tryscript.md` | 10.8 |
| `tests/test_cli_main.py` | 7.6 | `cli-api-shell.tryscript.md` | 9.1 |

Each time is from a single run.
CI runners differ in speed from run to run, and this record does not measure by how
much. The goldens are an example: they took 181.2 seconds on the base and 148.4 on the
tip, and nothing here says how much of that is the change between the commits.
Read a difference between two runs as a change in the suite only when it is large, or
when a second pair of runs repeats it.

## Differences From the Survey

The review’s survey of 2026-09-30 counted `a896d8fe` by hand.
`make test-report REFS=a896d8fe` reproduces its file and line counts for the Python
tests, the helper modules, `tests/dom`, and `tests/golden`, and its count of tryscript
commands. Two figures differ, and the tool’s are the ones to compare against from here
on:

- **Test functions:** the survey counted 2,899 and the tool counts 2,933. The survey
  matched `def test_` at the left margin, which leaves out the 34 methods of test
  classes. The tool reads each module’s syntax tree and counts what pytest collects.
- **`tests/fixtures`:** the survey counted 59 files and 10,236 lines, and the tool
  counts 62 files and 10,250 lines.
  The survey left out three files: two Markdown fixtures with non-ASCII names, which
  hold 14 lines, and one image.

## How a Pull Request Reports Its Change

The review accepts a change on the same numbers before and after it:

```shell
# Sizes, from the pull request's base to its working tree.
make test-report REFS="<base branch> ."

# Run time, from the `test (3.13)` job of the latest CI run on each branch.
make test-report REFS="<base branch>" LOG=base.log
make test-report LOG=head.log
```

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
