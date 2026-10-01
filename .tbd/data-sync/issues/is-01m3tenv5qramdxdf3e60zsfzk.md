---
type: is
id: is-01m3tenv5qramdxdf3e60zsfzk
title: "Tests: inventory and route suites — move envelope assertions to --api goldens and drop the provider tests the contract suite repeats"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:43:51.860Z
updated_at: 2026-10-01T00:43:51.860Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. These suites pre-date the stack; the three largest inventory files were read in full, the rest sampled. Wall-clock gates and leaked process state in these files are in the isolation bead.

## Scope

- Inventory: `tests/test_inventory_provider_contract.py` (2,006 lines, 47 tests), `tests/test_python_inventory_provider.py` (1,235, 30), `tests/test_browser_inventory.py` (1,439, 48), `tests/test_inventory_coordinator.py` (862), `tests/test_inventory_walk_work.py` (503).
- Routes and lifespan: `tests/test_browser_events_route.py` (812), `tests/test_rollup_route.py` (476), `tests/test_browser_walk.py` (421), `tests/test_browser_recent.py` (339), `tests/test_browser_inventory_api.py` (337), `tests/test_browser_lifespan_e2e.py` (207), `tests/test_browser_watch_backends.py` (491).
- Plugins: `tests/test_plugin_loader.py` (1,009, 44 tests).
- Goldens that cover the same routes: `tests/golden/cli-api-nav.tryscript.md`, `cli-api.tryscript.md`, `cli-api-shell.tryscript.md`, `cli-walk.tryscript.md`.

## Findings

1. The contract suite is legitimate; keep it. There is one provider (`src/metabrowser/inventory_engine/providers/python_inventory.py`), but the suite is provider-neutral and has a second consumer: `explorations/fdu-inventory-adapter/run.py:105-117` runs its 20 conformance cases against the fdu spike and records 3 failures, so it discriminates.
2. The provider's own tests re-assert the contract suite through the same public handle. `tests/test_python_inventory_provider.py:84-142, 145-178, 215-221, 252-303, 478-495, 799-802` repeat `tests/test_inventory_provider_contract.py:608-619, 1046-1245, 1779-1858, 1948-1972`. One assertion is unique and must move first: `catalog_tail.work.entries_visited == 0` (`tests/test_python_inventory_provider.py:134`). Rule: "Keep overlapping execution when tests protect different public interfaces or narrow a failure to different layers."
3. One failure, three patches. `tests/test_browser_inventory.py:1071-1085, 1088-1115` and `tests/test_python_inventory_provider.py:950-990` all show "walker raises, so status is failed" by patching different internals. Rule: "Cover externally distinct failures, not every internal fallible call that produces the same public error."
4. Route envelope tests duplicated by `--api` goldens. Each builds a fake request and asserts loosely (`in (...)`, `>=`) where the golden pins the full envelope:
   - `tests/test_browser_events_route.py:538-559` and `cli-api-shell.tryscript.md:207-221`; `:687-712` and `:231-258`; `:745-774` and `:70-99`.
   - `tests/test_rollup_route.py:75-98` and `cli-api-nav.tryscript.md:34-217`.
   - `tests/test_browser_recent.py:301-339` and `cli-api-nav.tryscript.md:389-420`; `:270-298` and `:344-383` (the `window=garbage` 400 has no golden yet).
   - `tests/test_browser_inventory_api.py:128-189` and `cli-api.tryscript.md:30-66` (the `depth=0` tallies have no golden yet).
   - `tests/test_browser_lifespan_e2e.py:70-133` re-asserts four of the above; `:182-207` writes no file despite its docstring.
5. In-process Python goldens of the walker. `tests/test_browser_walk.py:74-130, 237-296` record `walk_report`, `dump_tree` and the stream; `tests/golden/cli-walk.tryscript.md:28, 46, 57, 107, 145` record the same surfaces through the CLI. The tryscript fixture has no symlinks, so add them before deleting. `:108-109` asserts that the test's own expected literal lacks a substring.
6. Vacuous tests. `tests/test_browser_watch_backends.py:48-53` (literal subset of private constants), `:56-59` (`mode in` both possible values), `:88` (`isinstance(..., str)`); `tests/test_browser_events_route.py:810-812` and `tests/test_browser_recent.py:105` (constant equals literal); `tests/test_plugin_loader.py:79-81` (named `..._is_sdk_0_5`, asserts `"0.7"`); `tests/test_plugin_loader.py:758-770` (constructor echo); `tests/test_rollup_route.py:218-235` (branches on the outcome, so it passes either way).
7. Call-shape assertions. `tests/test_browser_inventory_api.py:89-126` records `max_rows` passed to a patched function; `tests/test_python_inventory_provider.py:762-792, 858-897`.
8. Repetition. `tests/test_plugin_loader.py` has 12 `test_manifest_rejects_*` (`:133-294, 702-730, 1001`) with no golden cover; 16 tests in `tests/test_browser_inventory.py` build inline `FsEntry` literals.
9. Source-text assertions. `tests/test_browser_walk.py:377-384`, `tests/test_browser_navigation.py:48-61, 351-368`, two `"FduInventory" not in source` tombstones (`tests/test_python_inventory_provider.py:1092-1108`, `tests/test_inventory_coordinator.py:291-292`), and `tests/test_browser_rollup.py:639-667` (a regex lint over `src` and `tests` that belongs in `devtools.lint`).

## Proposed restructuring

1. Routes to goldens. Add four golden blocks first (`/api/tree?depth=0`, `/api/recent?window=garbage`, `/api/rollup?ext_rank=popularity`, symlinks in `cli-walk`), then delete the tests in findings 4 and 5.
2. De-layer the inventory tests. Move `:134`, then delete the six duplicated provider tests and one crash duplicate; add an `FsEntry` test factory; parametrize the manifest rejections.
3. Delete findings 6 and 9 (tombstones and vacuous tests); move the rollup regex lint into `devtools.lint` with a negative probe.

## Expected reduction

- Step 1: about −600 lines of tests, about +90 lines of golden.
- Step 2: about −450 lines of tests.
- Step 3: about −100 lines.

## Acceptance

- The epic's accept rule.
- The four golden blocks land before the tests they replace are deleted.

## Must NOT be removed

- The 20 conformance cases and 27 contract-type tests in `tests/test_inventory_provider_contract.py`.
- `tests/test_active_tracker_event_loop_stall.py` (it counts blocking primitives; it is not a timing gate), `tests/test_inventory_walk_work.py`, `tests/test_navigation_tally_staleness.py:190-244`.
- `tests/test_inventory_coordinator.py`, `tests/test_content_trust.py`, `tests/test_serve_open_race.py`, `tests/test_e2e_filesystem_to_sse.py`.
- The private-store race tests at `tests/test_browser_inventory.py:692-751, 939-1033`: no public surface reaches them.

P3 and no release label: all of this is on `main`, unchanged by the stack.
