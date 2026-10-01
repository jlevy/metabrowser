---
type: is
id: is-01m3tej64v1fg6k1xkw5qd51pd
title: "Tests: convert app.js wiring pinned as source text into browserless sessions with goldens"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:41:52.024Z
updated_at: 2026-10-01T00:41:52.024Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Depends on the source-shape deletion bead, which removes the tests that are already covered so this one converts only what is left.

## Scope

About 150 Python tests (about 2,300 lines) that pin `app.js` wiring as text and have no executing evidence in `tests/dom`:

- `tests/test_browser_client_filestore.py:59-84, 203-268, 1043-1053` (pure helpers `sizeHtml`, `countHtml`, `formatAge`, `computeCellPatch`, `_treeSortKey`) and `:90-152` (EventSource backoff).
- `tests/test_quick_file_integration.py:140-251`.
- `tests/test_browser_recent_ui.py:313-332, 732-755`.
- `tests/test_source_append_js.py:80-112` (`loadMoreCurrentText`); `tests/test_source_line_anchors.py:131-134` says no session runs it.
- `tests/test_tree_keyboard_integration.py` (9 of 11 tests).

## Findings

1. These assert that a code string exists, for example `assert "sourceAppend.nextCacheValue(cached, chunk)" in load_more` (`tests/test_source_append_js.py:99`), with `following = load_more[append_call : append_call + 1_200]` (`:101`). A refactor that keeps the behavior breaks them, and a behavior change that keeps the string passes. AGENTS.md: "Browser-owned interaction state machines run browserlessly against the exact production JavaScript and have a golden session plus focused invariants."
2. The conversion pattern already exists. Seven `tests/dom` files lift `app.js` functions verbatim into `vm`: `tests/dom/source-kind-session.js:58-70, 112-116`; `tests/dom/preview-pane-state-session.js:307-345` (already lifts `_createInventoryEventSource`, `selectFile`, `activateNavPanel`); `tests/dom/subtree-freshness-behavior.js:10-17` (lifts `fileStoreApplyChangeInner`, `fetchSubtree`).
3. There is a per-fix habit. Commits 7e2296f3 and 26c9eb00 are feature commits whose only test evidence is new string assertions on `app.js`; 311e8398, ce2bf349 and 3488943f are test-only commits that re-pin strings after a refactor.

## Proposed restructuring

1. Extend `tests/dom/preview-pane-state-session.js` and `tests/dom/subtree-freshness-behavior.js`, and add one `shell-wiring-session.js` with a tryscript golden, covering: file-store and cell-patch helpers, EventSource backoff and catalog wiring, Recent wiring, tree-row activation and focus synchronization, and `loadMoreCurrentText` (append, failed render, fallback render, truncation banner).
2. Delete each Python text test as its behavior lands in a session, naming the golden line.
3. For DOM-heavy functions (`applyCellPatch`, `_insertRowSorted`), first move the decision into a small module the session can load, so the session does not grow a fake DOM. Stage those separately.

## Expected reduction

- Tests: about −2,300 lines of Python.
- Added: about +500 lines of session JS and about +400 lines of golden.
- Net about −1,400 lines, and the remaining evidence is executable.

## Acceptance

- The epic's accept rule.
- Each new session is registered in the functional parity table and `devtools/check_parity.py` stays green.
- No new general-purpose DOM stub is introduced.

## Must NOT be removed

- Any text test in the scope list until its session exists: today each is the only evidence for its behavior.
- The honest static contracts listed in the sibling bead.

P3 and no release label: medium risk, pre-existing on `main`, and it needs small production extractions; it should follow the release rather than gate it.
