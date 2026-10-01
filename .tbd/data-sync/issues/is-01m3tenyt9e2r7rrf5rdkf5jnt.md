---
type: is
id: is-01m3tenyt9e2r7rrf5rdkf5jnt
title: "Tooling tests and explorations: drop live-repo re-runs of lint, table-drive gate tests, and mark the superseded repository-cache measurements"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:43:55.589Z
updated_at: 2026-10-01T00:43:55.589Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Two related clean-ups outside the product's own tests: tests of gate tooling and experiment harnesses, and the experiment records shipped in the repository.

## Scope

- Tooling tests: `tests/test_performance_loop_gate.py` (1,514 lines, 55 tests), `tests/test_check_parity.py` (1,085, 42), `tests/test_browser_performance_capture.py` (778, 29), `tests/test_perf_instrumentation.py` (457), `tests/test_normalize.py` (203, 18), `tests/test_supply_chain.py`, `tests/test_docs_discipline.py`, `tests/test_git_arch_doc.py`.
- `explorations/`: `performance-loop` (45 files, 18,999 lines, on `main`), `repository-cache` (20 files, 12,797 lines, new in the stack: `measure.py` 3,446, README 437, 18 result JSON files 8,914), `fdu-inventory-adapter` (2,403).

## Findings

1. Live-repo re-runs of lint steps. Four tests re-assert on the real repository exactly what `make lint-check` already runs: `tests/test_supply_chain.py:54`, `tests/test_check_artifact_contracts.py:77`, `tests/test_check_parity.py:151` (which also executes every interaction session in Node, `devtools/check_parity.py:471`), `tests/test_docs_discipline.py:43`. Caveat: CI runs tests on four Python versions and lint on one. The synthetic positive and negative probes in those files are the real evidence and stay.
2. Example-heavy gate tests. About 20 tests in `tests/test_check_parity.py` share one 20-line shape (for example `:725-880`) and one six-line `.replace(` block recurs six or more times. `tests/test_normalize.py` is 18 one-assert tests with overlapping cases. Rule: "Collapse repeated examples into a parameterized case."
3. Tests of an experiment harness in the default loop. `tests/test_performance_loop_gate.py` pins the evidence-admission rules of `explorations/performance-loop/run.py`. No Make target or workflow executes that harness, but `docs/publishing.md:57-62` makes it a manual release step, so shrink rather than move: `:501-526` re-proves budgets pinned at `tests/test_web_performance.py:128-151`.
4. Source-text tests of harness scripts. 16 of the 29 tests in `tests/test_browser_performance_capture.py` assert strings in `explorations/performance-loop/*.js`; 13 more skip silently without Node.
5. Vacuous. `tests/test_perf_instrumentation.py:441-457` re-implements an environment parse and asserts its own expression, never reading `server._VERBOSE_REQUEST_LOG`. `tests/test_git_arch_doc.py:49-61` never opens the document it names.
6. `explorations/repository-cache` records largely the superseded design. Its suites `prefetch`, `lazy`, `autogc`, `fetches`, `precheck`, `lockdescriptors` and the blobless halves of `acquire` and `read` map to rows retired in `docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md:261-263`. The README never says so; its status line (`explorations/repository-cache/README.md:3`) still reads "Accepted on 2026-09-16 as the measured basis". The mapping was read at suite level, not per result row.
7. Nothing depends on the results. No test, devtools script or source file names a results file; docs link only README anchors. The results hold no absolute paths or usernames. The README states how to regenerate (`:38-47`).
8. Packaging. `explorations/` is not in the wheel. It appears to be in the sdist: neither the hatch `exclude` list (`pyproject.toml`) nor `REPOSITORY_ONLY_PARTS` in `devtools/check_distribution.py` names it. This was read from configuration; no sdist was built.
9. `explorations/fdu-inventory-adapter/evidence.json:34, 40, 64` embeds tracebacks with `<HOME>/.codex/worktrees/...` paths and stale line numbers. Rule: "Committed test data must not name the machine that recorded it."
10. `explorations/performance-loop/results/runs.jsonl` is 317 lines but 3.2 MB.

## Proposed restructuring

1. Delete the four live-repo re-runs, or keep one and say which Python-version evidence it adds.
2. Table-drive `tests/test_check_parity.py` (about 1,085 to 650 lines) and `tests/test_normalize.py` (203 to about 110).
3. Trim `tests/test_performance_loop_gate.py` by about 150 lines and parametrize `tests/test_browser_performance_capture.py` (about −155); delete finding 5.
4. For `explorations/repository-cache`: add a supersession note naming which suites still back a delivered decision (platform, umask, mailmap, storeconfig) and which measured a retired design. Ask the user whether the retired suites' results and their harness code stay in the tree or move to the reference branch with the Hosted Review code.
5. Add `/explorations/` to the sdist exclude and to `REPOSITORY_ONLY_PARTS`, after confirming by building.
6. Scrub or regenerate the fdu evidence file.

## Expected reduction

- Tests: about −900 lines (steps 1–3).
- `explorations/repository-cache`: 0 lines if only annotated; up to several thousand lines of results and harness if the retired suites move out. Not estimated per suite.

## Acceptance

- The epic's accept rule.
- A reader of `explorations/repository-cache/README.md` can tell which results describe the shipped design.
- `make build` shows the sdist no longer carries `explorations/`.

## Must NOT be removed

- Checker-logic tests on synthetic fixtures, including every negative probe in `tests/test_check_parity.py`.
- The repository-cache results that back surviving decisions: the README's disposition cites them.
- The evidence-admission tests for `cmd_compare` and `cmd_record` in `tests/test_performance_loop_gate.py`, while the harness remains a release step.

P3. Labelled `release:v0.12.0` for steps 4 and 5 only: the repository-cache record is new in the stack and its status line is wrong on the day it lands. Steps 1–3 can follow the release.
