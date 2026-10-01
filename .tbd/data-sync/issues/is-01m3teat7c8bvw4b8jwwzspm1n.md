---
type: is
id: is-01m3teat7c8bvw4b8jwwzspm1n
title: "Tests: delete the orphaned Hosted Review and oracle tests, and trim the contract-layer tests that survive the removal"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T00:37:50.382Z
updated_at: 2026-10-01T10:30:19.360Z
started_at: 2026-10-01T10:30:19.352Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Depends on mb-whmn (the removal PR); this bead covers what that removal makes deletable in tests and what is left to trim in the contract layer that stays.

## Scope

- Removed outright with the layer (4,579 lines of tests, 1,703 of fixtures):
  - `tests/test_hosted_review_*.py` (10 files, 3,228 lines, 126 tests), `tests/hosted_review_cases.py` (28), `tests/dom/hosted-review-model-behavior.js` (123).
  - `tests/test_github_coverage.py` (1,200 lines, 13 tests) and `tests/fixtures/github/oracle/` (11 files, 1,703 lines).
- Surviving contract-layer tests to trim: `tests/test_artifact_contract_registry.py` (754), `tests/test_check_artifact_contracts.py` (622), `tests/test_artifact_inventory.py` (493), `tests/test_capability_discovery.py` (200), `tests/test_distribution_policy.py` (298), `tests/test_plugin_public_api.py` (166), `tests/test_plugins_cli.py` (202), `tests/golden/cli-plugins.tryscript.md`.
- CI cost today: the ten hosted-review files take 18.7 s of the 269.9 s pytest run (`test_hosted_review_contracts.py` alone 18.0 s).

## Findings

1. Retired layer (class 11). `tests/test_github_coverage.py:14` imports `metabrowser.builtin_plugins.hosted_review.models`, so the removal breaks collection of all 13 tests. None touches the delivered pull-request view; no file under `src/metabrowser/builtin_plugins/github/` imports hosted_review or provider_resources. The oracle's only executable consumer is that file (`docs/project/architecture/arch-hosted-review-model.md:397`).
2. Vacuous even before the removal. `tests/test_github_coverage.py:618-627` tests `_resolve_pointer` and `:1182-1200` tests `_is_allowed_public_url`, both defined in the test file itself (`:62`, `:54`). Rule: "A test is vacuous when it verifies only facts established by its own setup."
3. Registry echo. `tests/test_artifact_contract_registry.py:159-160` asserts the registry contains what the test registered. `tests/test_artifact_inventory.py:246-255, 268-276` assert the fields the test's `_contract()` just set. `tests/test_plugin_public_api.py:115-125` asserts `X.__module__` and dataclass field names.
4. Repeated examples. `tests/test_check_artifact_contracts.py:138-574`: ten tests hand-roll the same ~28-line scaffold though `_browser_problems_for_module` (`:42-74`) exists. `tests/test_artifact_contract_registry.py:179-492, 738-754`: about 17 "malformed spec raises CapabilityRegistryError matching X" cases as 8–16-line literals each. Rule: "Collapse repeated examples into a parameterized case or a compact golden."
5. Redundant layering. `tests/test_check_artifact_contracts.py:77-78` re-runs on the live repo exactly what `make lint-check` runs. `tests/test_artifact_contract_registry.py:536-558, 596-643` repeat `tests/test_cache_records.py:243-288` through the same `validate_artifact` / `serialize_artifact`. `tests/test_plugins_cli.py:103-121` pins the doctor counts that `tests/golden/cli-plugins.tryscript.md:355-376` already records.
6. Source-shape guards for a layer that will not exist: `tests/test_distribution_policy.py:135-141, 243-245`; also `:162-171, 235-242` assert substrings of an embedded smoke script.
7. Mock echo. `tests/test_capability_discovery.py:84-100` asserts the mock was called with the group and returns the `CapabilitySet()` the test installed. Rule: "Never assert that a mock has the methods or values the test assigned to it."
8. Remnants of superseded designs with no production caller: `provider_resource_lock` / `LockKind.PROVIDER_RESOURCE` (only `src/metabrowser/cache/locks.py`), tested at `tests/test_cache_locks.py:143,151,173,274,543,551,559` and `tests/test_cache_async_locks.py:121`; `identity.provider_repository_store_id` (`src/metabrowser/cache/identity.py:124`), tested at `tests/test_repository_cache_contract_fixtures.py:199-221`.

## Proposed restructuring

1. In or directly after the mb-whmn removal PR: delete the files in the first scope list. Edit `tests/test_capability_discovery.py:12-16, 72-81, 168-186`, `tests/test_plugins_cli.py:106-120`, the doctor counts in `tests/golden/cli-plugins.tryscript.md:358-373`, and `tests/test_distribution_policy.py:135-141, 243-245`. Two gates need an edit in the same PR: `devtools/check_distribution.py:88-91` and `devtools/check_artifact_contracts.py:202-203`.
2. Trim the survivors: one `_rejects(match, **fields)` table for the registry rejections; parametrize the ten browser-evidence tests and assert the full problem list instead of 21 `assert any("x" in problem ...)` slices; delete findings 3, 5, 7.
3. Decide with the user whether the consumer-less generic parts go too (`ResourceProfileSpec`, `BrowserParserSpec` and `devtools/artifact-contract-browser-check.mjs`, the `frontmatter-md` profile). If they go, their tests go with them; if they stay, keep the tests and only table-drive them.
4. Remove the two dead remnants in finding 8 with their tests and fixture rows.

## Expected reduction

- Step 1: −4,579 test lines, −1,703 fixture lines, about −19 s of pytest time per job.
- Step 2: about −590 test lines (registry −220, check tests −370). If step 3 removes the consumer-less parts: about −1,100 to −1,250 instead.
- Step 4: about −120 test lines, −80 fixture lines.

## Acceptance

- The epic's accept rule.
- `metab --doctor` golden shows the post-removal counts and is reviewed line by line.
- No test imports `hosted_review` or `provider_resources` unless that module still ships.

## Must NOT be removed

- `tests/test_hosted_review_storage_models.py:165-185, 269-381`: the only tests of `ResourceProfileSpec.__post_init__`. Move them if `provider_resources` stays.
- `tests/test_hosted_review_contracts.py:475-505`: the only test of the bound `validation_context`. Move it or remove the code.
- `tests/test_capability_discovery.py:168-200` (failure caching), the registry trust-boundary tests (`tests/test_artifact_contract_registry.py:511-545, 577-593, 653-735`), the corpus-engine negatives (`tests/test_artifact_inventory.py:279-493`), the synthetic doc-table tests (`tests/test_check_artifact_contracts.py:81-135`), and `tests/test_cache_records.py`.
- Negative guards that keep retired designs gone: `tests/test_cache_acquire.py:376-377, 447-469`, `tests/test_git_store_read_policy.py:41-43, 133-164`, `tests/test_git_process.py:40-53`, `tests/test_cli_acquire_error_modes.py:223-259`.

Labelled `release:v0.12.0`: the removal lands before the release, and leaving its orphaned tests in place would break collection.

## Notes

2026-09-30: PR #246 (mb-whmn) already deletes the hosted-review tests (3,379 lines), the browser-model session, the GitHub coverage oracle and tests/test_github_coverage.py (2,903 lines), tests/test_capability_discovery.py and the profile/browser/provider cases in the contract tests (about 1,415 lines). What remains for this bead after #246 lands in the stack: trim the surviving contract-layer tests (the estimated -590 to -1,250 lines) and confirm nothing else for the retired layer is left.
