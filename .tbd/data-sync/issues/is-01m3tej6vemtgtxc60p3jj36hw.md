---
type: is
id: is-01m3tej6vemtgtxc60p3jj36hw
title: "Tests: one Node runner for tests/dom, and let the session goldens own what Python re-asserts"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies:
  - type: blocks
    target: is-01m3tekwar2fhzsmfyyby736pg
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:41:52.748Z
updated_at: 2026-10-01T00:42:47.504Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. The Node-absent gate itself is in the skips-and-tiers bead; the shared DOM shim is the sibling bead.

## Scope

- `tests/test_*_js.py`: 53 files, 2,919 lines, 101 tests. 18.5 s in CI.
- Session wrappers new in the stack: `tests/test_source_kind_session.py` (222), `test_source_freshness_session.py` (341), `test_source_ref_selector_session.py` (188), `test_github_pull_page_session.py` (421), `test_source_line_anchors.py` (187), `test_inert_toc.py` (162), `test_inert_html.py` (421).
- `tests/dom`: 94 files, 37,949 lines. 71 files (27,638 lines) are run only by pytest; 23 (10,311 lines) are also run by a `cli-ui-*` golden.
- `tests/golden/cli-ui-*.tryscript.md`: 15 files, 4,762 lines, 23 commands.

## Findings

1. The wrappers are one template. 32 files (967 lines) contain only: skip if Node is missing, `subprocess.run(["node", script, ...])`, `returncode == 0`, a marker check. `tests/test_markdown_mount_js.py:43-249` is 13 more copies; more in `tests/test_git_browser_js.py:43-52`, `tests/test_search_controller_js.py:20-34`, `tests/test_file_type_taxonomy_js.py:39-62`. The success marker has five shapes, and two files check none (`tests/test_folder_rollup_projection_js.py`, `tests/test_folder_totals_view_js.py`). Rule: "Collapse repeated examples into a parameterized case."
2. Four suites run twice. `tests/test_browser_keyboard_js.py:12-17` runs keyboard-shortcuts, overlay-layer, keyboard-help and tree-keyboard-navigation; each also has its own wrapper.
3. Python holds a second full copy of what a golden pins. The same command runs in the golden, so the golden is the evidence:
   - `tests/test_html_preview_js.py:30-92` equals `tests/golden/cli-ui-html-preview.tryscript.md:16-85`.
   - `tests/test_agent_log_plugin_behavior_js.py:31-59` equals `cli-ui-agent-log-charts.tryscript.md:16-54`.
   - `tests/test_asset_loader_js.py:37-107` equals `cli-ui-navigation.tryscript.md:710-711`.
   - `tests/test_source_append_js.py:54-77` and `tests/test_file_navigation_lazy_asset_js.py:30-81` are subsets of `cli-ui-file-lifecycle.tryscript.md`.
   - `tests/test_image_preview_js.py:30-79` and `tests/test_chart_theme_behavior_js.py:32-66` (matched by grep, not line by line).
   - `tests/test_preview_pane_state_js.py:70-222` mostly restates `cli-ui-file-lifecycle.tryscript.md:168-700`.
   - Replay asserts in `tests/test_source_freshness_session.py:309-341`.
   Golden guideline: layer "targeted assertions for critical invariants", not a second copy.
4. One case matrix asserted three times. `applyRecentChangeBatch` is called directly in `tests/dom/tree-filter-model-behavior.js:564-666`, in `tests/dom/recent-filter-session.js:155-203` with an inline expected matrix at `:205-309`, and printed in `cli-ui-navigation.tryscript.md:216-346`. None adds failure localization the others lack.
5. Two golden blocks pin only assertion labels. `cli-ui-navigation.tryscript.md:466-520` (catalog-feed, 51 labels) and `:573-703` (navigation-route, about 125 labels) record `{"verified": [...]}`. `check()` pushes the label before it evaluates the condition (`tests/dom/catalog-feed-behavior.js:25-32`, `tests/dom/navigation-route-behavior.js:13-20`), so an assertion weakened to `check(label, true)` leaves the transcript unchanged. These blocks are the parity evidence for `navigation.catalog-continuity`, `navigation.route-identity` and `navigation.pull-page-history`; `devtools/check_parity.py:630-700` requires only the command and status 0. Golden anti-pattern 2: "Narrow extractions pass silently even when the data has unexpected content."
6. `cli-ui-navigation.tryscript.md:710-711` is a single 1,300-character JSON line; its diffs cannot be reviewed.
7. Repeated examples in JS. `tests/dom/git-panel-behavior.js:751-800, 824-920` (about 50 `assertContains` on two rendered strings); `tests/dom/navigation-route-behavior.js:113-180` (about 90 `equal(label, ..., literal)`); `tests/dom/binary-byte-format-behavior.js:80-85` (six point checks subsumed by the loop at `:69-78`).
8. Source-text checks inside JS: `tests/dom/tree-node-name-behavior.js:103-117` counts occurrences of a call in `app.js`; `tests/dom/path-selector-escaping.js:79-95`; `tests/dom/folder-overview-behavior.js:126-129`.
9. Each parity session runs three times per `make verify`: under `check_parity` (lint), the pytest wrapper, and tryscript.

## Proposed restructuring

1. One runner. Add `tests/test_dom_behaviors.py`: a manifest of (script, args, success marker), parametrized, with one marker convention. Add a check that every `tests/dom/*-behavior.js` is in the manifest or run by a golden, and assert the manifest's length so an empty selection cannot pass. Delete the 32 template files, the template functions elsewhere, and `tests/test_browser_keyboard_js.py`.
2. Goldens own session output. Delete the Python copies in finding 3, keeping relational invariants (`tests/test_preview_pane_state_js.py:95-96, 104-107, 157, 192-194, 213`; `tests/test_github_pull_page_session.py:393-398`). Delete `tests/dom/recent-filter-session.js:205-309, 895-921` and `tests/dom/tree-filter-model-behavior.js:564-666`.
3. Make catalog-feed and navigation-route print label-to-actual-value rows so the golden shows state. Pretty-print the asset-loader JSON.
4. Table-drive the blocks in finding 7.

## Expected reduction

- Step 1: about 1,250 lines of Python down to about 90.
- Step 2: about −750 to −900 lines of Python and about −235 lines of JS.
- Step 3: goldens about +150 lines; JS about −200 lines of expected literals.
- Run time: about four fewer Node spawns for finding 2; the triple execution in finding 9 is left to the tiers bead.

## Acceptance

- The epic's accept rule.
- The count of `tests/dom` scripts executed by `make test` is the same before and after, shown in the PR.
- `devtools/check_parity.py` stays green; the exact golden commands it requires are unchanged.

## Must NOT be removed

- The 71 pytest-only `tests/dom` files: sole evidence for their modules. Consolidate their launchers, never drop them.
- The success markers: a script whose promise never settles exits 0 with no output.
- Fixture-recording tests (`test_recording_is_what_...` in the four session wrappers; `tests/test_inert_toc.py:64-123`): they make the session inputs real server output.
- Cross-language differentials: `tests/test_source_line_anchors.py:71-128`, `tests/test_file_type_taxonomy_js.py:20-36`, `tests/test_plugin_sdk_behavior_js.py:67-92`, `tests/test_preview_pane_state_js.py:225-237`.
- `tests/test_catalog_unicode_order_js.py`'s 100k gate; `tests/dom/tree-filter-model-behavior.js:39-130` and `tests/dom/markdown-mount-behavior.js:199-253` (localization the goldens lack).

No release label: the wrappers pre-date the stack. Finding 5 is the exception worth doing early, because those blocks are parity evidence that cannot fail.
