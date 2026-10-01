---
type: is
id: is-01m3tesntkscpn8he8rvbkj8gc
title: "Tests: one shared git and request fixture module, and immutable repositories built once instead of per test"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:45:57.409Z
updated_at: 2026-10-01T00:45:57.409Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Cross-cutting: test helpers copied between modules, and repositories rebuilt for every test. Do this after the isolation bead so shared fixtures rest on reliable resets.

## Scope

- Helper modules: `tests/git_pin_harness.py` (95 lines), `tests/source_mirror_fixture.py` (218), `tests/cache_home_fixture.py` (249), `tests/github_pull_fixture.py` (667), `tests/github_origin.py` (124), `tests/diff_fixture_repo.py` (109), `tests/inventory_harness.py` (70).
- Run time at the tip (CI `test (3.13)`): 269.9 s of pytest against 64.0 s on `main`. The top 20 files take 160.7 s.

## Findings

1. Test modules used as libraries. 49 imports from other test modules, 21 of them from `tests.test_cache_acquire` (`_file_source`, `_git`, `_allow_installed_git`), 8 from `tests.test_cli_golden`, 7 from `tests.test_cli_cache_acquire_golden`. Importing a test module collects its fixtures and couples unrelated files.
2. Copied helpers. `_git` is defined 15 times and `_git_env` 10 times. `_build_store`, `_hash_blob`, `_index_info` and `_delete_store_blob` are duplicated verbatim between `tests/test_git_revision_content_routes.py:95-176` and `tests/test_git_tree_source.py:97-164`. `_pinned_client` (`tests/test_git_revision_content_routes.py:232-255`) duplicates `tests/git_pin_harness.py`. `_settle` exists three times (`tests/test_github_pulls.py:1041`, `tests/test_github_serve.py:86`, `tests/test_github_pull_page_session.py:161`). Fake request, query and header classes are defined 53 times in 34 files. The inventory settle loop exists three times (`tests/test_inventory_provider_contract.py:135`, `tests/test_python_inventory_provider.py:63`, `tests/inventory_harness.py:26`). Rule: "Keep one authoritative copy of a fixture."
3. A repository per test. The new git and source files have no module- or session-scoped fixture: 32 of 33 tests in `tests/test_git_revision_content_routes.py` build a store (17 at 8 git spawns each); about 36 runs in `tests/test_source_refresh.py` each build an origin, acquire and serve, including 12 route-safety runs (`:517-546`) that assert nothing changed; `tests/test_source_refs.py` does about 18 git spawns for each of 25 runs; `tests/test_serve_pin.py` about 24 origin builds; `tests/test_cache_update.py:116-132` builds a mirror for 29 tests, 13 of them read-only; 50 of 59 tests in `tests/test_github_pulls.py` use the per-test `stand` (`:131-147`). Rule: "reduce redundant setup, share immutable fixtures ... batch process startup."
4. Costly single tests. `tests/test_refresh_signals.py` is 3 cases in 29.8 s; each writes 64 MiB of random data (`:57`). `tests/test_cache_update.py:783-850` writes 48 MiB and `:288-307` creates 2,000 refs.
5. The fake `gh` is a Python script (`tests/github_pull_fixture.py:53`), so each refresh starts about 8 interpreters.

## Proposed restructuring

1. One git fixture module (extend `tests/git_pin_harness.py`): `git`, `git_env`, `build_store`, `file_source`, `allow_installed_git`, `pinned_client`. Port the copies and stop importing from `tests.test_*`.
2. `fake_request` and `served_root` fixtures in `tests/conftest.py`; one settle helper in `tests/inventory_harness.py`.
3. Module- or session-scoped immutable origins and stores, copied per test only where the test mutates them (LFS config, deleted blob, `update-ref` at `tests/test_git_revision_routes.py:219-222`). Subjects stay per test because batch readers are bound to the event loop.
4. Build the large object for the signal tests once per module and reuse it.

## Expected reduction

- Lines: about −350 in the git and source files, plus about −300 across the fake-request and settle copies (estimates).
- Run time: not measured. The target is the 110 s spent in the 24 admitted-Git files and the 20 s in `tests/test_github_pulls.py`; report the measured change.

## Acceptance

- The epic's accept rule.
- No test module imports from another `tests.test_*` module.
- Per-file CI durations for the ten slowest files are reported before and after.

## Must NOT be removed

- Private stores for tests that mutate a store.
- Per-test homes for the permission, lock and crash-safety tests: sharing would hide the state they check.
- The real-signal tests themselves.

No release label: a refactor with medium risk that does not change what is tested; it should not sit on the landing path.
