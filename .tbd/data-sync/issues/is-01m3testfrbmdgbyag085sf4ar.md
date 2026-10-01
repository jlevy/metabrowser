---
type: is
id: is-01m3testfrbmdgbyag085sf4ar
title: "Tests: make absent tests loud — require Node and git, name the tiers, and record or fix every raised timeout"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T00:46:02.227Z
updated_at: 2026-10-01T04:49:35.288Z
started_at: 2026-10-01T04:49:35.282Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Cross-cutting: tests that can be absent while the gate is green, tests that never run in CI, timeouts without a measurement, and what belongs in a named outer tier.

## Scope

- CI: `.github/workflows/ci.yml` runs `make test` on ubuntu for Python 3.12, 3.13, 3.14 and 3.14t, and `make test-admitted-git` on ubuntu for Git 2.43.7 and 2.50.1. No macOS or Windows job.
- At the tip, CI collected 3,787 items and skipped 27; `main` skipped 0.
- Global pytest timeout: 60 s, `timeout_method = "thread"` (`pyproject.toml`).

## Findings

1. Node skips are unguarded. 176 `node`-absent skip sites in 66 test files (`pytest.skip("node not available")` and variants). Nothing turns a missing Node into a failure; there is no equivalent of `METABROWSER_REQUIRE_ADMITTED_GIT` (`tests/admitted_git.py`, `.github/workflows/ci.yml:166`). `docs/e2e-testing.md` says "CI provides Node and treats those contracts as required"; that holds only because `make test` also runs tryscript. The documented `uv ... pytest` path goes green without running the 71 pytest-only `tests/dom` files (27,638 lines). Rule: "A missing external dependency must fail setup loudly or be its own selectable test tier. It must never silently skip a test the suite is believed to run." CI at the tip had no Node skips.
2. Git skips are unguarded. `skipif(shutil.which("git") is None)` in 33 files. `make test` runs pytest without `-rs`, so a skip shows only as a count.
3. macOS-only tests never run in CI. 15 `darwin_only` ACL tests in `tests/test_cache_permissions.py` (marker at `:123`) and 4 case-insensitive-filesystem tests (`tests/test_cache_update.py:416, 465, 532`, `tests/test_github_pulls.py:1328`) skip on every CI run; they run only on a developer's Mac. No bead tracks this. From `ci-and-gates-rules`: "Single-platform blindness ... a matrix across the supported platforms is the only thing that catches per-platform semantics before a user does."
4. The live tier is undocumented and half of it cannot run. Selection is `METABROWSER_LIVE_GITHUB=1` plus the `live_github` marker; there is no Make target or CI job, and `docs/e2e-testing.md` does not mention it. `tests/test_github_pull_live_smoke.py` lacks the marker (fixed in the GitHub bead). `pytest.mark.timeout(600)` at `tests/test_github_live_smoke.py:46` and `tests/test_github_pull_live_smoke.py:36` has no recorded measurement.
5. Inner timeouts the global timeout pre-empts. With a 60 s thread timeout and no per-test override, these bounds cannot fire: `_SESSION_DEADLOCK_TIMEOUT_S = 300` (`tests/test_markdown_mount_js.py:40`, used 13 times; its comment records the measurement that motivated it, 11–23 s at load average about 170), `CHILD_TIMEOUT = 120` (`tests/test_cache_layout.py:67`, `tests/test_cli_cache_recovery_golden.py:82`), `timeout=120` at `tests/test_markdown_backslash_links.py:58`, `tests/test_cli_plugins_dir_merge.py:42`, `tests/test_cli_live_acquire_golden.py:128`, and `timeout_s=120` at `tests/test_refresh_signals.py:218`. Whether the thread timeout pre-empts in practice was read from configuration, not observed.
6. Unmeasured raised timeouts. `timeout=60` with no recorded measurement at `tests/test_inert_toc.py:150`, `tests/test_source_ref_selector_session.py:153`, `tests/test_source_kind_session.py:203`, `tests/test_github_pull_page_session.py:379`, `tests/test_source_freshness_session.py:306`, `tests/test_inert_html.py:93, 231`, `tests/test_github_check_tones.py:91`. Rule: "Raise a timeout only where it is genuinely tight ... and record the measurement that forced it."
7. `ADMITTED_GIT_TESTS` in the Makefile is a hand-maintained list of 24 files with no check that every caller of `require_admitted_git()` is in it.
8. The admitted-Git set runs six times. Those 24 files cost 109.5 s of the 269.9 s pytest run and run in all four `test` jobs and both `admitted-git` jobs. The runner's own Git in the tip's run was 2.55.0, which the floor admits, so the four `test` jobs and the two `admitted-git` jobs now differ only in Git version and in whether the floor is patched.
9. Costly evidence in the default loop. `tests/test_refresh_signals.py` (29.8 s for 3 cases), `tests/test_cache_update.py:288-307, 783-850`, `tests/dom/search-controller-profile.js` (wall-clock budgets). Rule: costly evidence goes "in a named outer tier ... State when that tier runs and which contract it covers."
10. Each parity session executes three times per `make verify`: under `devtools/check_parity.py`, in a pytest wrapper, and in tryscript.

## Proposed restructuring

1. One `require_node()` helper that fails when Node is absent unless an explicit opt-out is set, replacing the 176 skip sites; same for git. Run pytest with `-rs` in `make test`.
2. Assert the collected test count stays above a floor in CI (or report it in the job summary and fail on a drop), so an empty selection cannot pass.
3. Decide macOS coverage with the user: add a macOS job for the files that carry macOS-only tests (a named outer tier with a stated trigger), or record in a bead and in `docs/e2e-testing.md` that those 19 tests are developer-machine evidence.
4. Document the tiers in `docs/e2e-testing.md`: default, admitted-Git, live GitHub, and any slow tier, each with its trigger and the contract it covers. Add a Make target for the live tier.
5. Fix the timeouts: either raise the per-test pytest timeout where the inner bound is meant to apply, with the measurement beside it, or lower the inner bound below 60 s.
6. Generate or check `ADMITTED_GIT_TESTS` from the callers of `require_admitted_git()`.
7. Measure, then decide whether the costly tests in finding 9 run in every matrix job or once (for example in the admitted-Git job, which already exists). Decide the same for the six-fold run in finding 8.

## Expected reduction

- Lines: about −350 (176 skip sites become one helper call or a module-level requirement).
- Run time: if the 24 admitted-Git files ran on one Python version in the `test` matrix instead of four, about 110 s less in each of three jobs. This needs the user's decision on what the matrix must prove.

## Acceptance

- The epic's accept rule.
- Removing Node from PATH makes `uv ... pytest` fail, shown in the PR.
- Every skip that remains in CI output is named in `docs/e2e-testing.md` with its reason and tier.
- Every timeout above the global default has a recorded measurement.

## Must NOT be removed

- The admitted-Git job and its `METABROWSER_REQUIRE_ADMITTED_GIT` gate: it is the model for the Node gate.
- The gh guard in `tests/conftest.py` and its terminal summary.
- The platform skips with a stated reason (POSIX-only locks, signals, modes): correct on the platforms CI runs.

Labelled `release:v0.12.0`: findings 1 and 3 are evidence the release is believed to have and may not.
