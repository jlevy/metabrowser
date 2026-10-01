---
type: is
id: is-01m3teqnqm0pdjtjg7dsmnwzkj
title: "Tests: reset process-global state in conftest, and replace sleeps and wall-clock asserts with events and counts"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m3tesntkscpn8he8rvbkj8gc
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:44:51.825Z
updated_at: 2026-10-01T00:45:57.409Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Cross-cutting: process-global state that leaks between tests, waiting by sleep, and timing asserted against the wall clock.

## Scope

- `tests/conftest.py` (221 lines): autouse resets for capabilities, the served mirror and response caches.
- Process-global state in `src/metabrowser/source.py:518-524` (`_session`, `_generation`, `_subject_opener`, `_open_failure`, `_owned_subject`), `src/metabrowser/mirror_refresh.py` (`_served_mirror`), the served root set through `server._set_root_dir`.
- 90 `time.sleep` / `asyncio.sleep` call sites in `tests/*.py`, 34 of them in files the stack added; 9 real timer waits in `tests/dom/git-panel-behavior.js` (handled in the DOM shim bead).

## Findings

1. The source session is not reset between tests. `tests/conftest.py:109-116` resets only the served mirror. About 50 manual `reset_source_session()` calls are spread over 20 test files. On 2026-09-24 this failed CI on all Python versions: commit 2a2ec603 explains that a shell test "leaves the lazily opened source session behind, so every recorded generation came out one higher", and fixed it with one local reset at `tests/test_source_ref_selector_session.py:75`. Rule: "Do not depend on test execution order or on another test's side effects."
2. The same defect is still latent in a sibling. `tests/fixtures/source-freshness-responses.json` records literal generations 1 to 7; its recorder `tests/test_source_freshness_session.py:149-168` has no reset before recording (only at `:263`), so it passes today because of the alphabetical serial order. Tests that leave a bumped generation behind: `tests/test_source_session.py:78-112, 115-134, 274-288`, `tests/test_git_api.py:181-187` (every test), `tests/test_git_e2e.py:195`. (Inferred from reading; not run in a shuffled order.)
3. The served root leaks. `server._set_root_dir(` is called 321 times in 52 test files with three restore idioms; `tests/test_rollup_route.py` (14 calls) and `tests/test_content_trust.py` (12) do not restore at all.
4. Wall-clock assertions on host scheduling. `tests/test_navigation_tally_staleness.py:119-153` asserts `call_ms < 50` and `heartbeat_ms < 50` while a thread sleeps 0.35 s; the same file's docstring (`:196-201`) records this 50 ms heartbeat failing at 102 ms under load. `tests/test_browser_inventory.py:1036-1068` asserts `< 0.05` s against a `sleep(0.1)`; `:1317-1343` already shows the count-based alternative. `tests/test_browser_rollup.py:325-371` asserts `elapsed_ms < 1_000` with no recorded measurement. `tests/test_python_inventory_provider.py:715-718`, `tests/test_cache_async_locks.py:257`, `tests/test_source_refresh.py:401`, `tests/test_acquire_stall_and_hangup.py:118`. Three closed beads (mb-087n, mb-0e23, mb-7u5b) are flakes of this kind. Rule from `ci-and-gates-rules`: "An absolute wall-clock threshold on a heterogeneous shared runner often measures runner contention rather than the change."
5. Synchronization by sleep. `tests/test_browser_lifespan_e2e.py:145` (0.5 s); `tests/test_python_inventory_provider.py:464`; `tests/test_navigation_tally_staleness.py:75, 104, 127, 136` (where `:93` shows the injectable clock); `tests/test_cache_locks.py:320`; `tests/test_cache_update.py:822` (0.02 s "long enough for Git to be transferring", a race the test diagnoses itself at `:832`); `tests/test_git_process_group.py:124` (a 0.2 s window the cancellation must land in; on a loaded machine the test passes on the ordinary path); `tests/test_git_store_read_policy.py:181`; `tests/test_source_refresh.py:583`; `tests/test_cli_main.py:820`. Rule: "Never sleep to wait for something."
6. Short negative waits that can only false-pass. `tests/test_inventory_coordinator.py:437, 849`, `tests/test_browser_active_tracker.py:230`, `tests/test_acquire_stall_and_hangup.py:198`.
7. Un-timed waits on a child. `readline()` with no bound at `tests/test_cache_locks.py:107, 116`, `tests/test_cache_async_locks.py:79, 94`, `tests/test_cache_reclaim.py:122`, `tests/test_cache_update.py:713`; `join` results ignored at `tests/test_cache_locks.py:237, 322, 347`. Rule: "Give concurrent tests bounded timeouts so a deadlock fails with context."
8. `tests/test_refresh_signals.py:67-70` picks a port by bind-then-release, which another process can take.

## Proposed restructuring

1. Add an autouse fixture to `tests/conftest.py` that resets the source session before and after each test, and one that restores the served root. Delete the manual resets and restores. Add the missing reset to the freshness recorder.
2. Prove order independence once: run the suite in a different module order (for example reversed) in the PR and record the result. Do not add a new dependency for this.
3. Convert the wall-clock gates in finding 4 to counted work or event order; move the 40k-entry budget in `tests/test_browser_rollup.py:325` to `devtools/bench_serving.py`.
4. Replace the sleeps in finding 5 with an event or a poll on observable state with a bound; replace finding 6 with a positive signal.
5. Give every child `readline()` a bound and check `is_alive()` after `join`.

## Expected reduction

- About −150 lines (roughly 50 reset calls and their try/finally blocks, plus restore boilerplate).
- Run time: small. The value is removing a class of order-dependent and load-dependent failures.

## Acceptance

- The epic's accept rule.
- The suite passes in the default and in the reversed module order.
- No test asserts an absolute elapsed time unless it is in a named benchmark tier.

## Must NOT be removed

- Bounded polls on observable state (`tests/inventory_harness.py:39`, `tests/test_source_refresh.py:130`, the `_fetch_group` loop in `tests/test_refresh_signals.py`): these are correct.
- `sleep(0)` loop handoffs in the coordinator and provider tests: deterministic.
- `tests/test_active_tracker_event_loop_stall.py`: it counts blocking primitives with `sys.setprofile`; its 5 s deadline is a deadlock breaker, not a budget.
- The relative generation comparisons (`tests/test_source_refresh.py:232, 244, 257, 523, 546, 715, 778`): these are the right way to assert a generation.

Labelled `release:v0.12.0`: finding 1 already broke the integrated stack once, and finding 2 will do so again when the test order changes during landing.
