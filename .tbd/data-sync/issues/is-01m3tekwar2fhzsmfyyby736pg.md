---
type: is
id: is-01m3tekwar2fhzsmfyyby736pg
title: "Tests: one shared harness and DOM shim for tests/dom, with injected timers instead of sleeps"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T00:42:47.504Z
updated_at: 2026-10-01T00:42:47.504Z
---
Part of the test-suite review epic. Survey of a896d8fe, 2026-09-30, read-only. Do this after the Node runner bead so launchers are stable first.

## Scope

`tests/dom`: 94 files, 37,949 lines. 22 files define their own element, document or class-list stubs: 45 class definitions, 2,398 lines (counted with awk over `class` definitions), plus about 8 factory stubs.

## Findings

1. No shared shim. 16 `FakeElement`, 6 `FakeDocument`, 5 `Element`, 4 `FakeClassList`, 4 `FakeContainer`; `makeElement` four times. The only cross-require in the directory is `array-work-meter.js`. The seven largest `FakeElement`s each reimplement the same core of about ten methods: `tests/dom/git-panel-behavior.js:74-272`, `search-palette-behavior.js:52-234`, `source-line-anchors-session.js:64-231`, `tree-keyboard-navigation-behavior.js:43-186`, `diff-view-behavior.js:45-167`, `overlay-layer-behavior.js:7-123`, `keyboard-help-behavior.js:7-118`. Rule: "Keep one authoritative copy of a fixture." Repo rule (`docs/e2e-testing.md`): "Keep the shims small instead of growing an incomplete DOM implementation."
2. The copies disagree. `FakeClassList` is a Set in some files and a `className` string in others; `tests/dom/git-panel-behavior.js:131-147` regex-parses production markup inside the stub.
3. Assertion helpers are copied. `function check` is defined in 41 files, `equal` in 11, `assertEqual` in 7; three files use `node:assert`.
4. Setup outweighs assertion in the DOM-heavy files: git-panel 640 of 2,098 lines before the first assertion (31%), search-palette 340 of 1,052 (32%), diff-view 269 of 1,100 (24%).
5. Real sleeps. `tests/dom/git-panel-behavior.js:1248, 1361, 1366, 1393, 1410, 1663, 1673, 1730, 1741` wait `setTimeout(resolve, 10)` against `GIT_HOVER_DEBOUNCE_MS: 5`, though the sandbox timer is injectable (`:327`). Rule: "Never sleep to wait for something." Its sections also share one document and state (`:1906-1908, 2003-2004`).
6. Wall-clock gate in the default tier. `tests/dom/search-controller-profile.js:165-171` fails on budgets of 1 s, 5 s and 20 s; `tests/test_search_controller_js.py:53-62` re-asserts what the script enforces at `:150-160`.
7. Eight files rewrite `import`/`export` text before eval (for example `tests/dom/markdown-mount-behavior.js:113-133`), and twelve regex-extract functions from `app.js` and run them. These are behavioral but coupled to source shape.

## Proposed restructuring

1. Add `tests/dom/lib/`: one assertion harness (`check`, `equal`, the success marker) and one minimal element/document/class-list shim sized to what the seven largest stubs share. It replaces the copies; it must not grow into a general DOM.
2. Migrate file by file, largest first, running each file before and after.
3. Inject the timer in `git-panel-behavior.js` and drive the debounce deterministically; give its sections separate documents.
4. Move the wall-clock profile to a named outer tier or turn it into a count-based check.
5. One shared module loader for the import-rewriting files.

## Expected reduction

- About −900 to −1,200 of the 2,398 stub lines, about −250 lines of copied helpers.
- Nine real sleeps removed.

## Acceptance

- The epic's accept rule.
- The shared shim stays under a stated line budget recorded beside it, with the measurement of what the seven stubs needed.
- Every migrated file passes unchanged assertions.

## Must NOT be removed

- Any behavior assertion: this bead changes scaffolding only.
- File-specific stub behavior that a test depends on (for example focus order in the keyboard tests); keep it local and small.

P3 and no release label: medium-high risk, entirely pre-existing code, no user-visible effect.
