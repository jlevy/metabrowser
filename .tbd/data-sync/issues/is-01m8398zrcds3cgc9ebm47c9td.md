---
type: is
id: is-01m8398zrcds3cgc9ebm47c9td
title: "T5: File type chooser in the diff toolbar"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m8399315x37fjk00trntbhq6
  - type: blocks
    target: is-01m83998g7gxxf0k2vh9qk14j9
parent_id: is-01m83968ry3rs287s3mgg0r93y
created_at: 2026-11-23T04:05:24.873Z
updated_at: 2026-11-23T04:06:08.895Z
---
In `renderDiffToolbar` (`builtin_plugins/diff/diff-view.js`), for a diff of more than
one file, draw the File type menu with `filterControls.menuGroupHtml` (multi-select,
`anyLabel: "Any type"`, the T4 options and preset sections from the T3 tally) before the
layout control.

- Choosing types asks the plugin's `fetchComparison` for the `types=` answer (T2) and
  replaces the file sections, keeping the toolbar, layout, and current pin; disposes
  the replaced sections' hydration, Markdown views, and timers (replacement test).
- Prefetch per T7's result.
- A note says what is hidden ("12 of 35 files") with Clear; a filter that keeps nothing
  is a labeled state with Clear.
- A key for the menu through `mb.shortcuts`, chosen with the keymap's rules
  (docs/design-system.md, "Keys in a Menu"); `tests/test_keymap.py` pins the table.
- The selection model is a small pure module (selection transitions, request params,
  note text, empty-state decision) so it runs browserlessly.
- Parity: an interaction row `diff.type-filter` naming those functions, a
  `node tests/dom/diff-type-filter-session.js` session, and a
  `cli-ui-diff-type-filter.tryscript.md` golden. Design tokens only, no color literals.
- Verify in headless Chrome: a commit, a direct comparison, a PR Files tab; light and
  dark; narrow pane where the toolbar wraps.
