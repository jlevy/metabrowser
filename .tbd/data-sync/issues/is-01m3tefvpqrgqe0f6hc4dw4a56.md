---
type: is
id: is-01m3tefvpqrgqe0f6hc4dw4a56
title: "Tests: delete redundant and dead source-shape tests, and move the lint-like ones into a devtools check"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies:
  - type: blocks
    target: is-01m3tej64v1fg6k1xkw5qd51pd
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:40:35.786Z
updated_at: 2026-10-01T00:41:52.024Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. This bead removes source-shape tests that are redundant or dead and moves the lint-like ones into a check. Converting the uncovered ones to sessions is the sibling bead and must come after the deletions here.

## Scope

Python tests that read JS, CSS or HTML source text and assert substrings: 36 files, 11,544 lines, 509 tests. By reading, about 280 of the 509 assert code shape rather than behavior. Largest: `tests/test_browser_filter_ui.py` (1,410 lines, 79 tests), `tests/test_browser_client_filestore.py` (1,206, 68), `tests/test_browser_recent_ui.py` (991, 61), `tests/test_design_vocabulary.py` (857, 22). Nearly all pre-date the stack; the stack added three such tests to existing files and re-pinned about ten strings.

## Findings

1. Already executed by a DOM behavior test. `tests/test_browser_filter_ui.py:261-269, 284-292, 303-312, 450-457, 576-588, 591-601, 604-617, 1016-1025, 1034-1039` assert code strings in `filter-controls.js` and `filter-state.js`; `tests/dom/filter-controls-behavior.js:90-107, 123-128, 175-210` and `tests/dom/filter-state-behavior.js:97-126, 165, 239-302` execute the same behavior. `:613` pins a code comment. Repo rule (`docs/e2e-testing.md`): "Assert behavior and public contracts instead of copying implementation structure into the test."
2. Already pinned by a session golden. `tests/test_browser_filter_ui.py:324-332` (added by 7e2296f3) is covered by `tests/dom/source-kind-session.js:59-70` and `tests/golden/cli-ui-source-kind.tryscript.md:29`. `tests/test_browser_client_filestore.py:803-827, 725-761` are covered by `tests/dom/shell-delegate-owner-session.js:39-51, 185-190`. `tests/test_browser_recent_ui.py:365-373, 441-449, 674-679` are covered by `tests/dom/recent-filter-session.js` and `tests/dom/tree-filter-model-behavior.js:209-247, 454-562`.
3. A test of a test. `tests/test_browser_recent_ui.py:558-565, 626-638` read `tests/dom/recent-filter-session.js` and assert case names appear in its text; this passes with the case commented out. Rule: a test is vacuous when it "verifies only facts established by its own setup."
4. Windows that examine the wrong function. `tests/test_tree_keyboard_integration.py:33-35` slices a fixed number of characters from `function <name>`; at `:146-162` it reads 5,000 characters from `applyTreeFilters`, whose body is about 99 characters, so the assertions run over the next four functions. Slice counts by grep: filestore 53, filter_ui 52, recent_ui 28, tree_keyboard 17, loading_delay 14.
5. Unscoped substrings that cannot fail for the intended rule. `tests/test_browser_copy.py:35` (`"flex-direction: column;"`, 16 occurrences in `styles.css`), `tests/test_client_logical_ext.py:92-93` (`var(--muted)`, 73 occurrences), `tests/test_browser_filter_ui.py:190`, `tests/test_browser_client_filestore.py:913`.
6. Exact duplicates across files. The same string is asserted in `tests/test_browser_assets.py:34` and `tests/test_client_logical_ext.py:55`; activity-poll absence in `tests/test_browser_assets.py:39-48` and `tests/test_browser_client_filestore.py:926-938`; the fallback render in `tests/test_source_append_js.py:105` and `tests/test_source_line_anchors.py:145`.
7. Absence of long-gone code. `tests/test_legacy_view_renderers_gone.py` (8 of 9 tests), `tests/test_browser_client_filestore.py:534-536, 596-606, 926-938, 1131-1137`, `tests/test_browser_recent_ui.py:949-955, 961-971`, `tests/test_markdown_plugin_ownership.py:58-68`. `not in` assertions by grep: 67 in filter_ui, 39 in filestore, 29 in recent_ui.
8. A Python mirror of renderer markup. `tests/test_design_vocabulary.py:72-397` hand-builds an element tree "mirroring its renderer" and a CSS selector matcher (`:159-214`); renderer drift is invisible to it. Repo rule (`docs/development.md`): "Do not create a Python mirror of JavaScript behavior and do not grow a general fake DOM."
9. Lints written as tests. `tests/test_design_vocabulary.py` (17 of 22), `tests/test_loading_states.py`, `tests/test_browser_copy.py`, `tests/test_browser_loading_delay.py:27-126`, `tests/test_browser_filter_ui.py:466-559`. The repo already runs `devtools/check_tooltips.py` and `check_file_type_colors.py` in `make lint-check`.
10. Shell HTML asserted piecemeal. Ten files define their own index-render helper; the deferred-asset order is asserted four times (`tests/test_browser_recent_ui.py:143-158`, `tests/test_quick_file_integration.py:50-68`, `tests/test_tree_keyboard_integration.py:38-47`, `tests/test_keyboard_help_integration.py:32-43`); no golden pins the shell skeleton.
11. Stale justifications. `tests/test_client_logical_ext.py:5` ("No JS runtime in the test environment") and `tests/test_browser_client_filestore.py:5` ("We don't run the JS") are false: `tests/dom` runs under Node.

## Proposed restructuring

1. Delete findings 1–3, 6 and 7 (about 75 tests), naming the DOM test or golden line for each. Delete `tests/test_legacy_view_renderers_gone.py`, or keep one retired-token list in a check.
2. Replace `tests/test_plugin_sdk_helpers.py` (16 tests) with one `Object.keys(window.metabrowser)` listing in an existing session golden.
3. Add `devtools/check_design_vocabulary.py` to `make lint-check`, with a negative probe per rule and one shared CSS parser, and move the tests in finding 9 into it. Generate its rows from the real renderers or reduce it to a declared class list (finding 8).
4. Add one shell-skeleton golden and delete the roughly 20 piecemeal index-HTML tests.
5. Fix finding 4 and 5 for any text assertion that stays: scope it to the real function body or rule, or delete it.

## Expected reduction

- Tests: about −900 lines (step 1–2) and about −400 to −500 (steps 3–4).
- Goldens: about +15 lines (SDK surface) and about +80 (shell skeleton).

## Acceptance

- The epic's accept rule.
- The new check fails on its negative probes and is wired into `make lint-check`.
- If a paint-exempt row in `docs/project/architecture/arch-views-models-routes.md` names a file that moves, the row is updated and `devtools/check_parity.py` stays green.

## Must NOT be removed

- `tests/test_preview_frame_contract.py`: parsed structurally with negative controls (`:196-223`), and named by the `document.floating-ui-frame` paint-exempt row.
- CSS geometry tests in `tests/test_browser_filter_ui.py:150-172, 234-258, 675-725, 1246-1270, 1360-1397` and `tests/test_tree_keyboard_integration.py:251-263`: the `navigation.filter-layout` paint-exempt row cites them.
- `tests/test_index_cdn_origins.py`, `tests/test_untrusted_markdown.py`, `tests/test_inert_html.py`, `tests/test_kpress_dependency_contract.py`, the contrast and palette tests, `tests/test_notice_style.py`, `tests/test_chrome_typography.py`, `tests/test_skeleton_reserves_its_height.py`.
- `tests/test_browser_client_filestore.py:631-646, 764-800`; `tests/test_browser_filter_ui.py:272-281, 349-359, 1346-1351` (the DOM tests have no arrow-key or `data-active` coverage).
- Every text test of `app.js` wiring that no DOM test executes yet: those are converted in the sibling bead, not deleted here.

No release label: almost all of these tests are on `main` already, so this does not gate the v0.12 landing.
