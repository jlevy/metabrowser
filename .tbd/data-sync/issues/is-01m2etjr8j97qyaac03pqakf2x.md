---
type: is
id: is-01m2etjr8j97qyaac03pqakf2x
title: Add J and K as Down and Up aliases for keyboard list navigation
kind: feature
status: open
priority: 2
version: 1
labels:
  - keyboard
  - navigation
dependencies: []
created_at: 2026-09-14T02:05:18.481Z
updated_at: 2026-09-14T02:05:18.481Z
---
Add J and K as aliases for Down and Up wherever a list is navigated with the arrow keys. This is common practice (vim-style list navigation) and should behave identically to the arrows.

Scope:
1. File navigation tree (shortcut scope "tree", used by the Files and Recent views), in src/metabrowser/static/tree-keyboard-navigation.js registerCommands: add `{ key: "j" }` to `tree.next` (ArrowDown) and `{ key: "k" }` to `tree.previous` (ArrowUp). Same handler, same `repeat: true`.
2. Git panel commit list, in src/metabrowser/static/git-panel.js handleCommitRowKeydown: `j` behaves as ArrowDown and `k` as ArrowUp under the same guards (no modifiers, not composing, not defaultPrevented, tooltip dismissed).

Must not change:
- Text entry: J and K still type in inputs, textareas, selects, and contenteditable. The shortcut registry already skips editable targets for commands without allowInEditable; the Git panel handler must not fire from an editable target either.
- Quick File palette, filter menus and segmented controls, and the folder treemap keep their current keys. The palette has a text field, and the treemap's arrows are spatial.
- Modified keys: Shift+J/K, Ctrl, Alt, and Meta chords do not navigate. Modifiers are forbidden by default in the registry, which matches letters case-insensitively.
- Shift+ArrowUp/ArrowDown and Home/End keep their first and last item meaning; J and K get no first/last aliases.

Presentation: the Help overlay and aria-keyshortcuts list both bindings for Previous item and Next item (for example "↑ or K", "↓ or J").

Acceptance:
- tests/dom/tree-keyboard-navigation-behavior.js: j/k move focus like ArrowDown/ArrowUp, including repeat; J/K with any modifier do nothing; j/k typed in an editable target do not move the tree.
- keyboard-shortcuts-behavior.js and keyboard-help-behavior.js cover the added bindings' presentation.
- A Git panel commit-row test covers j/k movement and the modifier and editable guards.
- Goldens or parity rows that pin keyboard help output are updated; CHANGELOG Unreleased gets a user-visible entry.

No existing j/k bindings exist outside vendored code (checked on main a93ede3e).
