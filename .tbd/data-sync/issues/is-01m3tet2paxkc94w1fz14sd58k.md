---
type: is
id: is-01m3tet2paxkc94w1fz14sd58k
title: "Tests: record the baseline and make lines, durations and skips reportable for the review"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:46:10.625Z
updated_at: 2026-10-01T00:46:10.625Z
---
Part of the test-suite review epic. Do this first: the epic's accept rule needs the same numbers before and after every child.

## Scope

- A small reporting script under `devtools/` and a short section in `docs/e2e-testing.md` naming it.
- No test changes.

## Findings

1. The survey of 2026-09-30 produced the baseline by hand: `git grep -c ''` per ref for lines, and per-file durations derived from timestamps in the CI `test (3.13)` job log (run 36077428696 for the tip, 35634453594 for `main`). That is not repeatable by the next person.
2. CI does not report durations or skip reasons: `make test` runs plain `pytest` with no `--durations` and no `-rs`.
3. There is no coverage tooling. `uv.lock` has neither `coverage` nor `pytest-cov`, and `package.json` has no JS coverage tool, though `devtools/check_parity.py` already collects V8 coverage for owner functions. The testing guideline says "Line coverage is a discovery tool, not the definition of coverage."
4. Local timing is unreliable on a loaded machine: the survey could not run `pytest --durations=50` because the load average stayed above 40.

## Baseline to record (measured 2026-09-30 at a896d8fe)

| Measure | Value |
|---|---|
| `tests/test_*.py` | 287 files, 83,818 lines |
| test helper modules | 1,839 lines |
| `tests/dom` | 94 files, 37,949 lines |
| `tests/golden` | 54 files, 17,373 lines |
| `tests/fixtures` | 59 files, 10,236 lines |
| pytest in CI | 3,787 collected, 27 skipped, 269.9 s |
| tryscript in CI | 278 blocks, 138.8 s |

Slowest files in CI: `tests/test_refresh_signals.py` 29.8 s, `tests/test_github_pulls.py` 20.4 s, `tests/test_hosted_review_contracts.py` 18.0 s, `tests/test_cache_update.py` 14.3 s, `tests/test_markdown_mount_js.py` 7.9 s, `tests/test_cli_main.py` 7.4 s, `tests/test_source_refresh.py` 7.2 s. Slowest goldens: `cli-cache-url-grammar` 20.5 s, `cli-github-pull` 18.6 s, `cli-github-urls` 16.4 s.

## Proposed work

1. `devtools/test_inventory.py` (standard library only): prints lines and file counts for Python tests, helpers, DOM JS, goldens and fixtures at the working tree or a given ref, as one table.
2. Add `--durations=25 -rs` to the pytest invocation in `make test` so every CI run records the slowest tests and names its skips.
3. Decide with the user whether to add `coverage` as a dev dependency for discovery (subject to the 14-day cool-off in `SUPPLY-CHAIN-SECURITY.md`). If yes, add a Make target that is not part of `make verify`. If no, say in the epic that contract coverage is judged by `devtools/check_parity.py` and by named evidence per removed test.
4. Record the baseline table above in the epic when this bead closes, and state how each child reports its delta.

## Expected reduction

None. This bead adds about 100 lines of tooling so the other beads can be measured.

## Acceptance

- `make verify` is green.
- Running the script at `origin/main` and at the tip reproduces the survey's line counts.
- A CI run shows the slowest 25 tests and the skip reasons.

## Must NOT be removed

Nothing is removed.

Labelled `release:v0.12.0`: it is small, and the other release-labelled children need it.
