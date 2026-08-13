# Feature: Contextual Keyboard Help and Tree Navigation

**Date:** 2026-08-12

**Author:** Metabrowser maintainers

**Status:** Draft; ready for implementation review

## Overview

Metabrowser has useful keyboard behavior, but no single place explains it and no single
system owns it. Quick File binds `/` and `T` in its own module, its dialog keeps a
separate hard-coded hint list, filter controls implement their own local arrow behavior,
and the file tree cannot receive keyboard focus at all.

This plan introduces one internal shortcut registry that is the source of truth for
dispatch, the full Help dialog, and compact contextual hints.
A persistent hint strip at the bottom of the navigation pane always advertises `?` for
Help and `/` or `T` for Quick File.
When focus is in the file tree, the strip adds the keys that are actually available
there. The index-progress row remains in the same footer stack immediately below the
hints.

The same work gives the file tree complete, conventional keyboard navigation.
Arrow keys traverse or open the tree only while a tree row has focus.
The preview pane does not capture them, so ordinary browser scrolling continues to work
there.

## Goals

- Add a compact Help dialog opened by `?` and by a visible pointer-accessible trigger
- Explain what Metabrowser does, link to the public GitHub homepage, and list every
  supported application shortcut
- Define each shortcut once and derive dispatch, Help rows, and contextual hints from
  the same descriptor
- Always show the Help and Quick File hints at the bottom of the navigation pane
- Add situational tree-navigation hints only while those commands are available
- Make every rendered file-tree row reachable and operable with a conventional ARIA tree
  keyboard model
- Preserve native browser scrolling and text-entry behavior outside an active
  application context
- Migrate Quick File’s global open keys and dialog hints onto the shared system without
  changing its search, focus restoration, or composition behavior
- Keep all new browser modules in the fully strict JavaScript type-checking project,
  with explicit disposal and focused DOM tests

## Non-Goals

- User-customizable or persisted key bindings
- Multi-key sequences, command chords, or a general command palette
- Plugin-contributed shortcuts or a new `window.metabrowser` SDK surface
- Tree multi-selection, range selection, drag-and-drop, rename, or deletion
- Filename typeahead in the tree; unmodified `T` remains the global Quick File command
- Replacing native browser scrolling, selection, link activation, or editable-control
  behavior
- Listing every standard browser or control key in Help; the dialog documents
  Metabrowser commands and the non-obvious tree contract
- A second overlay implementation; Help reuses the shared modal contract from the
  [menu and overlay plan](plan-2026-08-06-menu-primitives-and-file-actions.md)

## Background

### Existing keyboard behavior is fragmented

`static/search_palette.js` owns both a document-level listener for `/` and `T` and a
separate `HINT_GROUPS` constant for `ArrowUp`, `ArrowDown`, `Enter`, and `Escape`. The
dispatch and presentation can drift because they are different data.

`static/filter_controls.js` correctly implements local ARIA behavior for its menus and
radiogroups, while the settings control and Quick File each own separate Escape and
focus behavior. Those control-local conventions should remain local, but application
commands need one arbitration point so two global listeners cannot claim the same key.

### The file tree is pointer-only

`renderTreeNodes()` emits file, directory, and symbolic-link rows as unfocusable `<div>`
elements. The click delegate can toggle a directory or open a file, but Tab cannot enter
the tree and arrows have no tree meaning.
Live updates, filtering, recency source changes, lazy subtree loads, and pagination can
all replace or add rows, so making one first-paint row focusable is not enough.
Focus identity has to survive every render path.

### The navigation footer already has the right location

`#index-progress` is a non-scrolling footer below `.tree-content`. It appears only while
the inventory is scanning and already uses the intended quiet chrome treatment.
The shortcut strip belongs immediately above it as a separate region: it stays visible
when progress is hidden, and progress keeps its own polite live-region semantics.

### Overlay work is already planned

The [menu and overlay plan](plan-2026-08-06-menu-primitives-and-file-actions.md)
specifies a body-portaled modal controller with focus capture, focus restoration, Tab
containment, Escape routing, and disposal.
Help consumes that contract.
If the modal slice has not landed when this feature begins, the first implementation
step extracts that slice as shared infrastructure; it does not create a Help-only modal
that would later need replacement.

That plan’s minimal tree focus-order work is superseded by this plan’s complete tree
contract. Context menus and future row actions consume the tree navigator defined here
rather than adding another roving-tabindex implementation.

## Design

### Resolved Interaction Model

1. **`?` opens Help.** Matching uses `KeyboardEvent.key === "?"`, so the normal
   Shift+slash gesture works across layouts that produce that character.
   Ctrl, Alt, and Meta combinations are never claimed.
2. **Quick File keeps both aliases.** Plain `/` and unmodified `T` open the same finder.
   The displayed keycap is uppercase by convention, but the binding is the unmodified
   letter: Shift+T is not claimed, while Caps Lock reporting `T` with no Shift remains
   accepted as it is today.
3. **Editable content wins.** Printable global shortcuts do nothing in `input`,
   `textarea`, `select`, or contenteditable targets, during IME composition, or after
   another handler has prevented the event.
   Typing `?`, `/`, or `t` in Quick File or a plugin control inserts text normally.
4. **The hint strip tells the truth about focus.** Help and Quick File are global and
   always shown. Tree commands appear only while a tree row owns focus.
   Moving focus to the filter bar, header, preview, or a dialog removes those contextual
   hints.
5. **Tree keys stay in the tree.** Arrow keys, Home, End, Enter, and Space are claimed
   only for a focused tree row.
   The same keys in the preview retain default browser behavior, including arrow, Page
   Up, Page Down, Home, End, and Space scrolling.
6. **Focus and selection remain distinct.** The roving focus row is where the next
   keyboard command applies.
   The selected file is what the preview displays.
   Moving with arrows does not fetch a file; Enter or Space activates it.
7. **No first-release tree typeahead.** Single-character typeahead would collide with
   the global `T` command and introduce buffering and timeout policy.
   Quick File is the explicit filename-navigation surface.

### Shortcut Matrix

| Context | Keys | Behavior |
| --- | --- | --- |
| Anywhere outside editable content | `?` | Open Help |
| Anywhere outside editable content | `/`, `T` | Open Quick File |
| File tree | `ArrowUp`, `ArrowDown` | Focus the previous or next visible tree row |
| File tree | `ArrowLeft` | Collapse an expanded folder; otherwise focus its parent |
| File tree | `ArrowRight` | Expand a collapsed folder; otherwise focus its first visible child |
| File tree | `Home`, `End` | Focus the first or last visible tree row |
| File tree | `Enter`, `Space` | Toggle a folder or open a file or symbolic link |
| Quick File | `ArrowUp`, `ArrowDown` | Change the active result |
| Quick File | `Home`, `End` | Move to the first or last mounted result |
| Quick File | `Enter` | Open the active result |
| Quick File | `Escape` | Close and restore prior focus |
| Help | `?`, `Escape` | Close and restore prior focus |

Tab and Shift+Tab keep their ordinary browser meaning except inside a modal, where the
shared modal controller contains focus.
They are not advertised as Metabrowser shortcuts.

### Shortcut Registry

A new strict module, `static/keyboard_shortcuts.js`, exposes an internal frozen factory
as `window.MetabrowserKeyboardShortcuts`. It is core-shell infrastructure, not a public
plugin API.

Each command descriptor contains both behavior and presentation metadata:

```js
{
  id: "quick-file.open",
  label: "Quick File",
  group: "Anywhere",
  scope: "global",
  bindings: [
    { key: "t", display: "T", shift: false },
    { key: "/", display: "/", shift: false },
  ],
  surfaces: { help: true, navHint: "always" },
  allowInEditable: false,
  allowRepeat: false,
  run: () => {
    openQuickFile();
    return true;
  },
}
```

The registry owns four operations:

- `register(command)` adds one descriptor and returns a disposer;
- `activateScope(scope, {exclusive})` puts a context above lower-priority contexts and
  returns a disposer that removes exactly that activation;
- `snapshot(surface, {includeInactive})` returns immutable, ordered presentation data
  for Help or a hint surface;
- `subscribe(listener)` reports registration and active-scope changes so chrome can
  repaint without polling.

`dispose()` removes the document listener, all registered commands, and all
subscriptions. Components retain and call their registration and scope disposers when
they unmount.

The permanently active `global` scope has the lowest priority.
`tree` is active only while focus is within the tree.
Modal scopes such as `quick-file` and `help` sit above both and are exclusive barriers:
an unmatched key remains native browser input instead of falling through to a lower
application scope.
This prevents `/` from opening Quick File on top of Help, for example.
A modal can deliberately register a local form of a global command; Help registers `?`
as another way to close.
Overlapping bindings are allowed across scopes because priority resolves them;
registering the same normalized binding twice within one scope is an error caught by
tests rather than an order-dependent winner.

One capture-phase document `keydown` listener performs dispatch.
It ignores `defaultPrevented`, composition, disallowed modifiers, editable targets, and
repeated events unless the matching descriptor opts in.
It evaluates active scopes from highest to lowest.
Only a handler that reports the event handled causes `preventDefault()` and propagation
to stop. An inactive or unavailable command leaves the browser event untouched.

Matching uses `event.key`, not physical `event.code`, because the command is the
character the user produced.
Each descriptor declares its modifier policy explicitly; there is no blanket Shift
rejection because `?` normally requires Shift.
Quick File’s navigation commands opt into non-printable handling within their editable
query target; printable global commands do not inherit that exception.

Presentation surfaces never copy key labels or command names.
The full Help list asks for all commands marked for Help, including inactive contextual
commands. The nav hint strip asks for commands whose hint policy is `always` plus
commands in the currently active scope.
Quick File uses the same presentation helper for its local hint row, retiring
`HINT_GROUPS`.

### Help Dialog

Help is a compact modal popover portaled to `document.body`. It uses the shared modal
surface rather than the native Popover API because it contains several focusable
controls and needs the same focus, Escape, scrim, and disposal contract as Quick File.

The persistent `? Help` item in the nav hint strip is a real button and is the pointer
trigger. The adjacent `/` or `T` Quick File item is a button too.
Both expose `aria-keyshortcuts`; no one has to know a shortcut before discovering either
command.
Opening captures the previous focus; closing by Escape, the Close button, or the
scrim restores it when the element is still connected.

The dialog has a labelled title, `aria-modal="true"`, a visible Close button, and a
bounded scrolling body for short viewports.
It contains:

1. **What Metabrowser does.** Initial copy:

   > Metabrowser runs a local server for one folder.
   > Use the navigation pane and filters to explore its live file inventory; select a
   > file to open a preview in the main pane.
   > Built-in and trusted installed plugins provide views for different file types.

2. **Project link.** “Metabrowser on GitHub” points to
   `https://github.com/jlevy/metabrowser`, opens in a new tab, and uses
   `rel="noopener noreferrer"`.

3. **Keyboard shortcuts.** Registry-derived groups for Anywhere, Navigation, Quick File,
   and Help. Contextual groups say when they apply; an inactive context is not presented
   as disabled.

The description is intentionally short and links to the project instead of copying
installation, security, or plugin documentation into an in-app surface.

### Contextual Navigation Hints

The index template gains `#nav-shortcut-hints` immediately before `#index-progress`:

```text
┌─────────────────────────────────────────┐
│ …scrolling file tree…                   │
├─────────────────────────────────────────┤
│ [?] Help   [T] [/] Quick File           │  always
│ [↑][↓] move  [←][→] tree               │  while a tree row has focus
│ [Enter][Space] open or toggle           │
├─────────────────────────────────────────┤
│ ◌ Scanning 8,192 files…                 │  only while indexing
└─────────────────────────────────────────┘
```

The illustration is a content model, not fixed copy.
Actual labels come from the registry.
The strip uses the existing `.kbd` component and design tokens, wraps at narrow widths,
and never causes horizontal scrolling.
The persistent row remains one quiet band; contextual groups may wrap to a second line.

Persistent command hints render as quiet buttons; contextual tree hints are explanatory
text because their action target is the already-focused row.
The strip has an accessible label but is not an `aria-live` region.
Focus moving around the application must not repeatedly announce changing tips.
`#index-progress` retains its independent polite live region below it.

### File-Tree Semantics and Focus

A new strict module, `static/tree_keyboard_navigation.js`, owns the keyboard and focus
model. `app.js` continues to own fetching, rendering, selection, and lazy expansion; the
navigator receives callbacks for the existing toggle and open operations rather than
reaching into private fetch state.

The rendered structure follows the ARIA tree pattern:

- one dedicated row wrapper has `role="tree"` and an accessible name;
- each file, folder, symbolic link, and pagination action has `role="treeitem"` and an
  `aria-level`;
- folder child containers have `role="group"`;
- folders expose `aria-expanded`, updated at the same time as their visible state;
- the currently previewed leaf exposes `aria-selected="true"`;
- exactly one visible item has `tabindex="0"`; other items have `tabindex="-1"`.

Summary, truncation, empty, loading, and error rows stay outside the tree wrapper or use
presentational roles and never enter the roving order.
The “Show N more” action becomes a keyboard-operable tree item: Enter or Space mounts
the next page while retaining a valid focus target.

The roving anchor is stored by durable identity: row kind and served-root-relative path,
with the pagination action’s generated page identity as its temporary key.
A render synchronization step runs after root and recent paints, lazy subtree loads,
pagination, filtering, live insert/remove/type replacement, and selection changes.
Synchronization is coalesced during live-event bursts and performs these repairs:

1. preserve the same visible row when it still exists;
2. if it became hidden or was removed, choose its nearest visible sibling, then its
   parent, then the first visible row;
3. if actual focus was inside the replaced tree, move focus to the repaired row;
4. if focus was elsewhere, update only the future Tab stop and never steal focus.

The initial roving anchor is the selected file when it is rendered, otherwise the first
visible row. First paint never focuses the tree automatically.

Visible-row traversal excludes filter-hidden rows, descendants of collapsed folders,
unmounted pages, and placeholders.
The navigator keeps a synchronized visible-row snapshot rather than scanning the entire
mounted tree on every repeated arrow event.
An invalidation is cheap and coalesced; a key event forces one synchronous refresh only
when the snapshot is dirty.

Folder behavior matches the conventional tree model:

- Right on a collapsed folder expands it and leaves focus on the folder.
  A second Right moves to its first visible child after that child exists.
- Right on an expanded folder with no visible child does nothing.
- Left on an expanded folder collapses it and leaves focus on the folder.
- Left on a collapsed folder or leaf moves to its parent when one is rendered.
- Up and Down traverse the flattened visible order without opening a file.
- Home and End move to the first and last visible item.
- Enter or Space toggles a folder and activates a file, symbolic link, or pagination
  row.

Clicking a row also makes it the roving anchor, so pointer and keyboard use continue
from the same place.
Focus styling is separate from `.selected`: a focus ring says where keys apply, while
the existing selected treatment says what is open.

### Main-Pane Contract

The shortcut dispatcher has no `preview` bindings for arrows, Home, End, Page Up, Page
Down, or Space.
Those events are not prevented, so the browser scrolls the preview in the
usual way. Embedded links, controls, text selection, and plugin-provided editable
elements retain their native behavior.

Global Help and Quick File remain available when focus is on non-editable preview
content.
The editable-target guard applies to content rendered by plugins as well as core
controls.

### Component Boundaries

| Component | Responsibility |
| --- | --- |
| `static/keyboard_shortcuts.js` | Registry, scope arbitration, event matching, immutable presentation snapshots, disposal |
| `static/keyboard_help.js` | Registry-derived Help dialog and nav/Quick File hint rendering |
| `static/tree_keyboard_navigation.js` | Tree semantics, roving focus, visible-row traversal, activation callbacks |
| Shared `static/overlay_layer.js` | Modal portal, focus containment and restoration, Escape, scrim dismissal |
| `static/search_palette.js` | Search-specific state and results; registers its commands and consumes shared hints |
| `static/app.js` | Composition root, existing tree actions, synchronization calls, selection and source changes |
| `server.py` index template | Help trigger host, hint-strip host, script ordering |
| `static/styles.css` | Token-based Help, focus, and hint-strip presentation |

Every new factory accepts an injected `document` for DOM tests and returns a disposer.
The index loads the registry and overlay modules before consumers and loads `app.js`
last as it does today.

### API Changes

There are no HTTP, Python, command-line, persistence, or public plugin API changes.
The new `window.Metabrowser*` factories are internal script-composition seams like the
existing search modules.
They are not added to `window.metabrowser` and carry no compatibility promise for
plugins.

## Implementation Plan

### Phase 1: Registry, Help, and Shared Hints

- [ ] Write failing Node DOM tests for shortcut matching, scope precedence, editable
  guards, duplicate detection, handled-event semantics, subscriptions, and disposal
- [ ] Implement the strict shortcut registry and one document dispatcher
- [ ] Reuse or extract the shared modal slice specified by the menu and overlay plan
- [ ] Implement the Help dialog with the approved description, GitHub link, generated
  shortcut groups, focus restoration, and disposal
- [ ] Add the persistent nav hint host above index progress and render Help and Quick
  File from registry data
- [ ] Migrate Quick File open keys, modal scope, Escape, result-navigation commands, and
  hint rows without changing its search behavior
- [ ] Add static-asset ordering and package-data checks for every new module

### Phase 2: Tree Keyboard Navigation

- [ ] Write failing DOM tests for ARIA structure, roving focus, each tree key, focus
  versus selection, and unhandled preview/editable keys
- [ ] Add semantic root, group, tree-item, expanded, selected, level, and tabindex
  attributes to root, recent, lazy, paged, and live-update rendering paths
- [ ] Implement synchronized visible-row navigation and existing-action callbacks
- [ ] Preserve or repair the roving anchor across filtering, source replacement, lazy
  loads, pagination, insertion, removal, and type replacement
- [ ] Add focus-visible styling and contextual tree hints from the registry
- [ ] Validate pointer behavior, keyboard behavior, narrow navigation panes, light and
  dark themes, and screen-reader naming in a real browser
- [ ] Run `make verify` as the required handoff gate

## Testing Strategy

### Shortcut Registry

- exact matching for `?`, `/`, unmodified `t`, and Caps Lock `T`;
- Shift+T and Ctrl/Alt/Meta variants remain untouched;
- composition, editable targets, and already-prevented events remain untouched;
- modal scope wins over tree scope, which wins over global scope;
- repeat is accepted for tree movement and rejected for open/toggle commands;
- duplicate bindings in one scope fail deterministically;
- an unhandled command does not prevent browser behavior;
- registrations, subscriptions, active scopes, and the document listener dispose.

### Help and Hints

- Help opens from both `?` and the visible button, mounts once, and restores focus;
- title, dialog semantics, description, GitHub URL, link safety attributes, and Close
  control are present;
- Help rows and nav hints are derived from registry snapshots;
- Help and Quick File hints always render through `.kbd`;
- tree hints appear on tree focus and disappear when focus leaves;
- hint updates are not live-announced, while index progress remains polite;
- narrow widths wrap without covering or shrinking progress text.

### Tree Navigation

- one visible row is tabbable and no hidden row is;
- Up, Down, Home, and End follow visible order;
- Left and Right implement parent, child, collapse, and expansion behavior;
- Enter and Space toggle folders, open leaves, and activate pagination;
- arrow-only movement never fetches a preview;
- lazy expansion keeps focus stable and a later Right reaches the loaded child;
- filters, recency repaint, live changes, and removal repair the roving anchor;
- `aria-expanded`, `aria-selected`, `aria-level`, and focus state stay synchronized;
- arrows and Space in the preview retain default browser behavior.

### Integration and Real Browser

Python HTML tests verify script order and the footer structure.
Node DOM suites exercise deterministic interaction contracts.
A real-browser pass uses the public-safe manual fixtures from
[end-to-end testing](../../../e2e-testing.md) to verify focus rings, scrolling, pointer
parity, modal containment, responsive wrapping, both themes, and no unexpected console
errors.

## Acceptance Criteria

- Pressing `?` outside editable content opens an accessible Help dialog
- Help contains the approved Metabrowser description, the public GitHub link, and every
  supported shortcut grouped by context
- The nav footer always shows Help and Quick File, with contextual tree hints only when
  a tree row has focus
- The hint strip remains above index progress and does not alter progress announcements
- The registry is the only source for the commands and labels shown in Help or hints
- Every visible tree row is keyboard reachable through one roving Tab stop
- Folder, leaf, lazy, paginated, filtered, recent, and live-update rows preserve the
  specified keyboard and focus behavior
- Main-pane arrows and scrolling keys retain native browser behavior
- Quick File retains its current functionality and no global shortcut fires in editable
  content
- All new modules are strict, disposable, packaged in the wheel, and covered by DOM
  tests; `make verify` passes

## Rollout Plan

The feature is additive and needs no flag, stored preference, or migration.
Land the registry and Help phase first only if its public behavior is internally
complete; do not expose a registry without moving Quick File’s duplicated definitions.
Land tree navigation next, then keep this plan active until the real-browser and full
verification gates pass.

Release notes should call out `?` Help, the persistent shortcut strip, and keyboard tree
navigation together.
They are one discoverability feature, not separate implementation details.

## Open Questions

There are no blocking product questions.
Custom bindings, plugin command registration, tree typeahead, sibling expansion with
`*`, and pane-cycling shortcuts can be evaluated later against real usage.
The registry leaves room for them without implementing their policy now.

## References

- [Quick File finder and search providers](plan-2026-07-17-scalable-file-search.md)
- [Menu primitives and gated file actions](plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Filter controls and fine-grained navigation filtering](plan-2026-08-09-nav-filter-controls.md)
- [Design system](../../../design-system.md)
- [End-to-end testing](../../../e2e-testing.md)
- [Metabrowser on GitHub](https://github.com/jlevy/metabrowser)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
