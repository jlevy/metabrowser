# Feature: Contextual Keyboard Help and Tree Navigation

**Date:** 2026-08-12

**Author:** Metabrowser maintainers

**Status:** Implemented and validated

## Overview

Metabrowser has useful keyboard behavior, but no single place explains it and no single
system owns it. Quick File binds `/` and `T` in its own module, its dialog keeps a
separate hard-coded hint list, filter controls implement their own local arrow behavior,
and the file tree cannot receive keyboard focus at all.

This plan introduces one internal shortcut registry that is the source of truth for
dispatch, the full Help dialog, and compact contextual hints.
A persistent hint strip at the bottom of the navigation pane advertises `?` for Help and
`T` for Quick File — the two commands a reader has no way to guess.
It stays at that: tree commands live in Help rather than in the strip, and each command
shows one preferred key rather than every alias it answers to.
The index-progress row remains in the same footer stack immediately below the hints.

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
- Apply the [design-system](../../../design-system.md) contracts for canonical key
  names, shortcut grammar, Help copy, modal anatomy, tokens, focus, and overlay
  lifecycle on every surface
- Always show the Help and Quick File hints at the bottom of the navigation pane, one
  preferred key each, and nothing else
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
  [menu and overlay plan](../active/plan-2026-08-06-menu-primitives-and-file-actions.md)

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

The
[menu and overlay plan](../active/plan-2026-08-06-menu-primitives-and-file-actions.md)
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
2. **Quick File keeps both aliases.** Unmodified `T` and plain `/` open the same finder.
   The displayed keycap is uppercase by convention, but the binding is the unmodified
   letter: Shift+T is not claimed, while Caps Lock reporting `T` with no Shift remains
   accepted as it is today.
3. **Editable content wins.** Printable global shortcuts do nothing in `input`,
   `textarea`, `select`, or contenteditable targets, during IME composition, or after
   another handler has prevented the event.
   Typing `?`, `/`, or `t` in Quick File or a plugin control inserts text normally.
4. **The hint strip earns its line.** It carries only `?` for Help and `T` for Quick
   File, each shown as a single preferred key.
   Tree commands are omitted on purpose: arrows in a file tree are what a reader tries
   first without being told, so a permanent reminder spends space to teach nothing.
   Help remains the complete reference, including the aliases the strip does not name.
5. **Tree keys stay in the tree.** Arrow keys, Home, End, Enter, and Space are claimed
   only for a focused tree row.
   The same keys in the preview retain default browser behavior, including arrow, Page
   Up, Page Down, Home, End, and Space scrolling.
   Jump-to-edge is bound to Shift+Arrow as well as Home and End, because a Mac laptop
   has no Home key and fn+Left is not a shortcut anyone discovers.
6. **Selection follows focus.** Moving the roving focus with arrows, Shift+Arrow, Home,
   or End opens the row it lands on, so skimming costs one keypress per row, not two.
   Browsing is the common case, and a confirm keystroke bought nothing once opening was
   fast enough to be effectively free.
   Enter and Space are therefore action keys rather than view keys: they change a
   folder’s disclosure state or mount a deferred page, and never open.
   Arrow-driven opening replaces the route instead of pushing it, so a skim does not
   bury the reader’s entry point under one history entry per row passed.
7. **No first-release tree typeahead.** Single-character typeahead would collide with
   the global `T` command and introduce buffering and timeout policy.
   Quick File is the explicit filename-navigation surface.

### Shortcut Matrix

| Context | Keys | Behavior |
| --- | --- | --- |
| Anywhere outside editable content | `?` | Open Help |
| Anywhere outside editable content | `T`, `/` | Open Quick File |
| File tree | `ArrowUp`, `ArrowDown` | Open the previous or next visible tree row |
| File tree | `ArrowLeft` | Collapse an expanded folder; otherwise open its parent |
| File tree | `ArrowRight` | Expand a collapsed folder; otherwise open its first visible child |
| File tree | `Shift`+`↑`, `Shift`+`↓` (or `Home`, `End`) | Open the first or last visible tree row |
| File tree | `Enter`, `Space` | Toggle a folder or show the next page |
| Quick File | `ArrowUp`, `ArrowDown` | Change the active result, wrapping at both ends |
| Quick File | `Home`, `End` | Move the query caret to the start or end of the line |
| Quick File | `Enter` | Open the active result |
| Quick File | `Escape` | Close and restore prior focus |
| Help | `?`, `Escape` | Close and restore prior focus |

Tab and Shift+Tab keep their ordinary browser meaning except inside a modal, where the
shared modal controller contains focus.
They are not advertised as Metabrowser shortcuts.

### Approved Groups and Command Copy

Group identifiers resolve to this exact ordered copy:

| Group ID | Help heading | Context sentence |
| --- | --- | --- |
| `anywhere` | Anywhere | Available outside text fields. |
| `navigation` | Navigation | Available while a file-tree row has focus. |
| `quick-file` | Quick File | Available while Quick File is open. |
| `help` | Help | Available while Help is open. |

Command descriptors own the following copy.
The key column shows formatter output, not strings stored by the command.
An em dash means the command appears in full Help but is not selected for a compact hint
surface.

| Command ID | Group | Keys | Label | Help description | Compact hint |
| --- | --- | --- | --- | --- | --- |
| `help.open` | `anywhere` | `?` | Help | Open Help for a description of Metabrowser and all keyboard shortcuts. | Help |
| `quick-file.open` | `anywhere` | `T` or `/` | Quick File | Find and open a file from the current folder. | Quick File |
| `tree.previous` | `navigation` | `↑` | Previous item | Open the previous visible item in the file tree. | — |
| `tree.next` | `navigation` | `↓` | Next item | Open the next visible item in the file tree. | — |
| `tree.parent-or-collapse` | `navigation` | `←` | Parent or collapse | Collapse the focused folder or open its parent item. | Navigate folders |
| `tree.child-or-expand` | `navigation` | `→` | Child or expand | Expand the focused folder or open its first visible child. | Navigate folders |
| `tree.first` | `navigation` | `Shift`+`↑` or `Home` | First item | Open the first visible item in the file tree. | — |
| `tree.last` | `navigation` | `Shift`+`↓` or `End` | Last item | Open the last visible item in the file tree. | — |
| `tree.activate` | `navigation` | `Enter` or `Space` | Toggle folder | Expand or collapse the focused folder, or show the next page. | Toggle folder |
| `quick-file.previous` | `quick-file` | `↑` | Previous result | Move to the previous Quick File result, wrapping at the top. | Move |
| `quick-file.next` | `quick-file` | `↓` | Next result | Move to the next Quick File result, wrapping at the bottom. | Move |
| `quick-file.activate` | `quick-file` | `Enter` | Open result | Open the active Quick File result. | Open |
| `quick-file.close` | `quick-file` | `Esc` | Close Quick File | Close Quick File and restore focus to the previous control. | Close |
| `help.close` | `help` | `?` or `Esc` | Close Help | Close Help and restore focus to the previous control. | — |

### Design-System Contract

This feature is the first complete consumer of the design system’s
[keyboard-command](../../../design-system.md#keyboard-commands-and-help) and
[overlay](../../../design-system.md#overlays-menus-and-dialogs) contracts.
The contracts are implementation requirements, not visual guidance.

| Concern | Single owner | Required consumers |
| --- | --- | --- |
| Event matching and scope | Shortcut registry | Global commands, Help, Quick File, tree commands, future menu commands |
| Key names and binding grammar | Shared binding formatter | Help, nav hints, Quick File hints, menu hints, `aria-keyshortcuts` |
| Command and context copy | Command and group descriptors | Help, compact hints, visible triggers |
| Portal, modal state, focus, Escape, inert background, and disposal | Shared overlay controller integrated with the registry | Help, Quick File, menus, future dialogs |
| Keycap and floating-surface presentation | `.kbd`, dialog/menu primitives, and semantic tokens | Every rendered instance in core and plugins |

The binding formatter maps semantic keys to canonical keycap and spoken forms plus an
ARIA form when the physical shortcut is representable accurately.
For this release the visible vocabulary is `?`, `/`, `T`, `↑`, `↓`, `←`, `→`, `Shift`,
`Home`, `End`, `Enter`, `Space`, and `Esc`; the spoken form expands symbols and
abbreviations. Because `?` and `/` are matched as produced characters, their physical
chords vary by keyboard layout and are omitted from `aria-keyshortcuts`; the
layout-stable `T` alias is advertised for Quick File.
Alternatives use the word “or,” so Quick File is shown as `T` or `/`, never as adjacent
keycaps or with a slash used as a separator.
Keycaps use `.kbd`; call sites neither write display labels nor apply key styling.

Every Help-visible descriptor supplies a sentence-case label and a complete,
active-voice description.
Every compact-hint descriptor supplies a one-to-three-word sentence-case hint without
terminal punctuation.
The copy does not repeat its keys.
Group identifiers resolve through one ordered group registry, which owns the group title
and its context sentence.

Help uses the shared modal-dialog anatomy even though its surface is compact: labelled
header, visible Close control, bounded scrolling body, modal semantics, inert
background, focus containment and restoration, and token-only presentation.
“Popover” describes its visual size only and is not its role.
The Help implementation introduces no local surface colors, type sizes, shadows, radii,
z-index values, key abbreviations, or focus rules.

Conformance is protected at the data, DOM, and browser levels.
Descriptor tests reject incomplete copy and unknown keys; renderer tests exercise the
same sample bindings across Help, nav, Quick File, and menu-hint output; overlay tests
cover every open and close path; and the real-browser pass covers focus, zoom, narrow
widths, both themes, reduced motion, and spoken names.

### Shortcut Registry

A new strict module, `static/keyboard_shortcuts.js`, exposes an internal frozen factory
as `window.MetabrowserKeyboardShortcuts`. It is core-shell infrastructure, not a public
plugin API.

Each command descriptor contains both behavior and presentation metadata:

```js
{
  id: "quick-file.open",
  group: "anywhere",
  scope: "global",
  copy: {
    label: "Quick File",
    description: "Find and open a file from the current folder.",
    hint: "Quick File",
  },
  bindings: [
    { key: "t", modifiers: { shift: "forbid", ctrl: "forbid", alt: "forbid", meta: "forbid" } },
    { key: "/", modifiers: { shift: "forbid", ctrl: "forbid", alt: "forbid", meta: "forbid" } },
  ],
  surfaces: { help: true, navHint: "always" },
  control: quickFileDialog.control,
  allowInEditable: false,
  allowRepeat: false,
  run: (context) => {
    openQuickFile(context.trigger);
    return true;
  },
}
```

`group` is an identifier, not display copy.
An ordered group registry supplies “Anywhere” and the context sentence used by Help.
The formatter maps `key` and `modifiers` to the canonical visible, spoken, and ARIA
forms; a binding cannot carry a caller-authored display label.

The controller provides these operations:

- `register(command)` adds one descriptor and returns a disposer;
- `activateScope(scope, {exclusive})` puts a context above lower-priority contexts and
  returns a disposer that removes exactly that activation;
- `invoke(commandId, context)` runs the named command through the same active-scope and
  availability checks used by keyboard dispatch and carries an optional pointer trigger
  to the handler, so visible buttons neither bypass the command system nor depend on
  click-to-focus browser behavior;
- `present(commandId)` returns the immutable copy, binding description, shortcut ARIA,
  and optional control binding for one command regardless of active scope;
- `snapshot(surface, {includeInactive})` returns immutable, ordered presentation data
  for Help or a hint surface;
- `subscribe(listener)` reports a structured registration or active-scope change so
  chrome can update without polling or rebuilding unaffected controls;
- `describeBindings(bindings)` returns keycap labels, one expanded spoken phrase, and an
  `aria-keyshortcuts` serialization only for accurately representable physical bindings;
  and
- `appendBinding(parent, description)` emits the one accessible `.kbd` DOM structure
  shared by Help, nav, Quick File, and menu hints.

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

The overlay controller does not add a second document-level Escape listener.
A surface component registers its close descriptor for its lifetime so full Help can
include it while the surface is closed.
Opening activates its registry scope; closing removes that activation, and disposal
removes both the activation and descriptor.
An anchored popup inside a modal has the highest active scope, so the first Escape
closes that popup and the next can close the modal.
Focused widget roots may still own their conventional arrow, Home, End, Enter, Space,
and Tab behavior; those local listeners are not application-wide shortcut dispatchers.

Matching uses `event.key`, not physical `event.code`, because the command is the
character the user produced.
Each descriptor declares its modifier policy explicitly; there is no blanket Shift
rejection because `?` normally requires Shift.
Quick File’s navigation commands opt into non-printable handling within their editable
query target; printable global commands do not inherit that exception.

Presentation surfaces never copy key labels or command names.
The full Help list asks for all commands marked for Help, including inactive contextual
commands.
The nav hint strip carries only the two commands a reader cannot guess: `?` for
Help and `T` for Quick File.
Tree commands are registered, dispatched, and listed in full Help, but claim no space in
the strip — arrows in a file tree are the first thing anyone tries unprompted, so
advertising them permanently costs a line and teaches nothing.
The strip also shows a single preferred key per command rather than every alias, so
Quick File reads `T` there while Help still documents `/`. The alias stays bound, and
`aria-keyshortcuts` still announces both.
Quick File declares no Home or End command at all: its query box is an editable
combobox, so those keys stay with the caret.
Quick File uses the same presentation helper for its local hint row, retiring
`HINT_GROUPS`. Descriptors that share a compact hint are coalesced only by the snapshot
helper, so the tree can show `↑` or `↓` with “Move” without introducing a second
grouping table.

### Help Dialog

Help is a compact modal dialog portaled to `document.body`. It uses the shared dialog
primitive rather than the native Popover API because it contains focusable controls and
needs the same focus, Escape, scrim, inert-background, and disposal contract as Quick
File.

The persistent `? Help` item in the nav hint strip is a real button and is the pointer
trigger. The adjacent `T` or `/` Quick File item is a button too.
The Quick File button exposes formatter-derived `aria-keyshortcuts="T"`. The
character-matched punctuation aliases remain visible and spoken but do not guess a
layout-specific physical chord for ARIA. No one has to know a shortcut before
discovering either command.
Opening captures the previous focus; closing by Escape, the Close button, or the scrim
restores it when the element is still connected.

The dialog uses the shared header, title, visible Close control, scrolling body, and
optional-footer anatomy.
It has a labelled title, `aria-modal="true"`, a bounded body for short viewports, and no
local surface tokens.
Background application content is inert until every close or disposal path restores its
prior state. It contains:

1. **What Metabrowser does.** Initial copy:

   > Metabrowser runs a local server for one folder.
   > Use the navigation pane and filters to explore its live file inventory; select a
   > file to open a preview in the main pane.
   > Built-in and trusted installed plugins provide views for different file types.

2. **Project link.** “Metabrowser on GitHub” points to
   `https://github.com/jlevy/metabrowser`, opens in a new tab, and uses
   `rel="noopener noreferrer"`. Its accessible description says that it opens in a new
   tab.

3. **Keyboard shortcuts.** Registry-derived groups for Anywhere, Navigation, Quick File,
   and Help. Every row uses the shared binding renderer and descriptor copy.
   Contextual groups say when they apply; an inactive context is not presented as
   disabled.

The description is intentionally short and links to the project instead of copying
installation, security, or plugin documentation into an in-app surface.

### Contextual Navigation Hints

The index template gains `#nav-shortcut-hints` immediately before `#index-progress`:

```text
┌─────────────────────────────────────────┐
│ …scrolling file tree…                   │
├─────────────────────────────────────────┤
│ [?] Help   [T] Quick File               │  always
├─────────────────────────────────────────┤
│ ◌ Scanning 8,192 files…                 │  only while indexing
└─────────────────────────────────────────┘
```

The illustration is a content model, not independent copy.
Actual labels, grouping, key abbreviations, separators, spoken names, and any valid
`aria-keyshortcuts` values come from registry snapshots and the shared binding renderer.
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
- each file, folder, symbolic link, and pagination action has `role="treeitem"`,
  `aria-level`, `aria-posinset`, and `aria-setsize`;
- each treeitem is labelled by its visible filename, folder name, or pagination action;
  age, size, and count metadata do not become part of the node’s accessible name;
- non-empty and lazy folder child containers have `role="group"` and an ID referenced by
  the owning folder treeitem’s `aria-owns`, preserving the current adjacent-sibling DOM
  while establishing the required parent relationship in the accessibility tree;
- folders with known or potential children expose `aria-expanded`, updated at the same
  time as their visible state; known-empty folders are end nodes and omit both
  `aria-expanded` and `aria-owns`;
- selectable file and symbolic-link leaves expose `aria-selected`, with only the
  currently previewed leaf set to `true`; folders and pagination actions omit selection
  state;
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
- Up and Down traverse the flattened visible order, opening each row they land on.
- Shift+Up and Shift+Down move to the first and last visible item, opening it.
  Home and End do the same on keyboards that have them.
- Enter or Space toggles a folder or mounts a pagination row, and never opens.

Clicking a row also makes it the roving anchor, so pointer and keyboard use continue
from the same place.
A click still fuses opening and toggling, because a pointer gets one gesture per row;
the keyboard splits them, because arrows already carry the opening half.
Focus styling is separate from `.selected`: a focus ring says where keys apply, while
the existing selected treatment says what is open.
Because selection follows focus, the two now travel together in the tree, but they stay
distinct treatments — a row can hold focus while a filter hides the selection it opened.

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
| `static/keyboard_shortcuts.js` | Registry, scope arbitration, event matching, descriptor validation, canonical binding formatting and rendering, immutable presentation snapshots, disposal |
| `static/keyboard_help.js` | Registry-derived Help dialog and nav hint rendering through shared dialog and binding primitives |
| `static/tree_keyboard_navigation.js` | Tree semantics, roving focus, visible-row traversal, activation callbacks |
| Shared `static/overlay_layer.js` | Modal portal, inert background, focus containment and restoration, registry-scoped Escape, scrim dismissal |
| `static/search_palette.js` | Search-specific state and results; registers its commands and consumes shared hints |
| `static/app.js` | Composition root, existing tree actions, synchronization calls, selection and source changes |
| `server.py` index template | Help trigger host, hint-strip host, script ordering |
| `static/styles.css` | Shared dialog anatomy plus token-based Help, focus, keycap, and hint-strip presentation |

Every new factory accepts an injected `document` for DOM tests and returns a disposer.
The index loads the registry and overlay modules before consumers and loads `app.js`
last as it does today.

### File and Function Map

The names and seams below are the implementation contract.
If implementation exposes a conflict, update this plan and the owning bead before
introducing a parallel helper or moving behavior across a boundary.

#### `static/keyboard_shortcuts.js`

This new strict module exposes `window.MetabrowserKeyboardShortcuts` and contains no
application-specific DOM.

- `KEY_DEFINITIONS` maps each supported semantic key to its event key, visible keycap,
  spoken name, and physical-key ARIA token or deliberate omission.
- `GROUP_DEFINITIONS` owns the fixed group order, Help headings, and context sentences.
- `normalizeBinding(binding)` validates keys and modifier policies and returns the
  normalized frozen value used everywhere else.
- `bindingSignature(binding)` produces the scope-local duplicate-detection key.
- `eventMatchesBinding(event, binding)` applies exact key and modifier policy without
  mutating the event.
- `isEditableTarget(target)` is the single input, textarea, select, and contenteditable
  guard used by printable global commands.
- `validateCommand(command)` rejects unknown groups and keys, duplicate IDs, missing
  Help or hint copy, and ambiguous surface or control bindings before registration.
- `describeBindings(bindings)` produces ordered keycaps, visible separators, one spoken
  phrase, and an `ariaKeyshortcuts` value only when every advertised physical shortcut
  is accurate.
- `appendBinding(parent, description)` emits the shared `.kbd`, separator, and
  screen-reader text structure without accepting caller-authored key labels.
- `create({document})` installs the one capture-phase document dispatcher and returns
  frozen `register`, `activateScope`, `invoke`, `present`, `snapshot`, `subscribe`,
  `describeBindings`, `appendBinding`, and `dispose` operations.

`snapshot()` sorts by group order and explicit command order, filters by active scope
unless `includeInactive` is true, and coalesces adjacent compact hints by group and hint
copy.
It carries any frozen surface-owned control binding into the immutable presentation
item. Registration order cannot change Help order.
`invoke(commandId, context)` returns false rather than running an inactive or
unavailable command and passes `context.trigger` to a handler only after those checks.
Only a true result from `invoke()` or the keyboard handler consumes an event.

#### `static/overlay_layer.js`

This new strict module exposes `window.MetabrowserOverlay`. This feature lands the modal
slice; point and element anchoring remain in the menu-and-actions plan.

- `focusableElements(root)` returns the current Tab order for focus containment.
- `captureBackgroundState(document, portal)` records the prior `inert` state of every
  body child outside the portal; `restoreBackgroundState(records)` restores those exact
  values on every close and disposal path.
- `createDialogShell({document, title, className})` builds the shared scrim, labelled
  dialog, header, title, visible Close button, scrolling body, and optional footer.
- `createModal({document, shortcuts, scope, closeCommandId, title, className, initialFocus, resolveFocusFallback})`
  owns one body portal, previous-focus capture, Tab containment, scrim dismissal,
  exclusive scope activation, focus restoration, single-modal arbitration, and disposal.
  The close descriptor must already be registered; the visible Close button and scrim
  call `shortcuts.invoke(closeCommandId)` and the button gets its action name and
  representable `aria-keyshortcuts` value from `shortcuts.present(closeCommandId)`. Its
  frozen `control` binding connects a trigger’s `aria-haspopup`, `aria-controls`, and
  `aria-expanded` state to the modal and restores the trigger’s exact prior state when
  disconnected.

The returned controller exposes `element`, `dialog`, `body`, `footer`, `control`,
`open(trigger)`, `close({restoreFocus})`, `isOpen()`, and `dispose()`. It adds no
document-level keydown listener; the close descriptor is registered through the shortcut
registry. Closing focuses the connected opening trigger first, then the consumer’s
connected fallback; it never guesses an unrelated control inside the generic overlay
layer. The dialog root may own its local Tab handler because Tab containment is widget
behavior, not an application shortcut.

#### `static/keyboard_help.js`

This new strict module exposes `window.MetabrowserKeyboardHelp`.

- `renderHelpGroups(body, snapshot)` rebuilds the ordered group headings, context
  sentences, command labels, descriptions, and shared binding structures from a Help
  snapshot.
- `reconcileHintStrip(host, snapshot, invoke)` preserves actionable Help and Quick File
  button nodes by command ID while adding or removing non-actionable contextual tree
  hints. It connects each button to the snapshot’s surface-owned control binding, calls
  `shortcuts.invoke(commandId, {trigger: button})`, and derives its shortcut
  presentation through the registry.
  The button’s accessible name remains the command label rather than including its
  keycap.
- `create({document, shortcuts, overlay, hintHost, resolveFocusFallback})` registers
  `help.close`, creates the shared modal against that command, then registers
  `help.open` with the modal’s control binding.
  It renders the approved description and safe GitHub link, subscribes both surfaces to
  registry changes, and returns `open`, `close`, and `dispose`.

Help renders all Help-visible commands with `includeInactive: true`; registration
changes rebuild those rows, while scope-only changes reconcile the nav strip.
The nav snapshot retains hints marked `always` even behind an exclusive inert modal and
adds contextual hints only from active scopes.
Keyed reconciliation never detaches the button that opened a modal, so focus restoration
returns to that exact control.
The hint host is never live-announced.
Disposing removes both command registrations, the registry subscription, and the modal
portal.

#### `static/search_palette.js`

The existing `create(options)` keeps search, listbox, status, and stale-result behavior,
but gains required `shortcuts` and `overlay` inputs.

- Remove `OPEN_KEYS`, `HINT_GROUPS`, `hintGroup()`, `isEditableTarget()`,
  `handleGlobalKeydown()`, and the palette-owned document listener.
- Add `registerCommands()` for `quick-file.open`, movement, activate, and close
  descriptors. Result commands opt into the editable query target; the printable global
  aliases do not. The query box is an editable combobox, so `Home` and `End` stay with
  its caret and the palette registers no first or last command; the movement commands
  wrap instead, which keeps both ends of the bounded list one keystroke away.
- Add `renderShortcutHints()` using the active Quick File snapshot and
  `appendBinding()`, with no local labels or key strings.
- Remove `handleInputKeydown()`. `Tab` belongs to the shared modal focus trap in both
  directions; a palette-local handler preempts it and strands reverse `Tab` on the query
  box. Composition and every advertised command route through the registry.
- Replace direct overlay construction and the local `open()` and `close()` focus
  lifecycle with `MetabrowserOverlay.createModal()`. Palette open and close hooks still
  reset search state, cancel work, and select the query.
  Forward the injected `resolveFocusFallback` callback for a tree or preview node
  replaced while Quick File is open.
  Register `quick-file.close` before constructing the modal, then attach the modal
  control binding to `quick-file.open`; Close, scrim, and Escape consequently call the
  same handler.
- Extend `dispose()` to remove command registrations and the hint subscription before
  disposing the modal.

The returned palette API remains `open`, `close`, `isOpen`, `element`, and `dispose`, so
`app.js` and existing callers do not acquire a second migration.

#### `static/tree_keyboard_navigation.js`

This new strict module exposes `window.MetabrowserTreeKeyboardNavigation` and receives
existing application actions as callbacks.

- `rowIdentity(row)` returns a durable `kind:path` identity or the pagination row’s
  generated page identity.
- `readVisibleRows(root)` builds the flattened mounted order while excluding filtered
  rows, collapsed descendants, placeholders, and rows being removed.
- `parentRow(row)` and `firstChildRow(row)` resolve structural movement from treeitem
  and group relationships rather than path parsing.
- `setAnchor(row, {focus, scroll})` maintains exactly one visible `tabindex="0"`,
  updates the durable anchor, and optionally moves focus and scrolls the row into view.
- `repairAnchor(previousSnapshot, nextRows)` chooses the same identity, nearest visible
  sibling, rendered parent, or first row in that order.
- `prepareForMutation()` captures the visible snapshot and whether focus is currently in
  the tree before an `innerHTML`, `outerHTML`, insertion, or removal path runs.
- `synchronize()` refreshes roles, owned-group relationships, level, position, set size,
  selected and expanded state, the visible snapshot, and the roving anchor.
  Repeated invalidations coalesce; a key command forces a refresh only while dirty.
- `registerCommands()` installs all navigation descriptors in the `tree` scope and
  delegates toggle, open, and pagination behavior through injected callbacks.
- `create({document, host, shortcuts, getSelectedPath, setFolderExpanded, activateRow})`
  owns delegated focus and pointer synchronization, activates the tree scope only while
  a treeitem has focus, and returns `prepareForMutation`, `synchronize`,
  `setSelectedPath`, `focusedRow`, and `dispose`.

Movement commands allow key repeat.
Activation does not.
Arrow-only movement changes focus but never calls `activateRow`.

#### `static/app.js`

`app.js` remains the composition and data-rendering shell.
It does not implement key matching or walk the visible tree for each key.

- Add application-lifetime `shortcutRegistry`, `keyboardHelp`, and `treeKeyboard`
  handles. `initKeyboardInfrastructure()` constructs them before `initQuickFileFinder()`;
  the Help subscription allows later Quick File and tree registrations to appear without
  initialization-order coupling.
- Add `resolveApplicationFocusFallback(previous)` to re-resolve a replaced tree row
  through `treeKeyboard.focusedRow()`, return `#preview-pane` for replaced preview
  content, or return null.
  Pass it to Help and Quick File; the overlay layer remains independent of application
  selectors.
- Tear the layer down on a real `pagehide` only.
  A persisted `pagehide` means the document entered the back/forward cache, and a
  bfcache restore never re-runs `DOMContentLoaded`, so disposing there would return the
  user to a page whose shortcuts, Help, Quick File, and tree keys are all silently dead.
  A persisted `pageshow` re-runs `initKeyboardInfrastructure()` and
  `initQuickFileFinder()`, both of which are idempotent.
- Add `treeRootHtml(content)` to wrap only navigable rows in
  `<div class="tree-root" role="tree" aria-label="Files">`. Summary, truncation,
  loading, error, and filter-note rows stay outside this root.
- Add `treeDomId(prefix, identity)` and
  `treeItemAttributes({kind, path, level, position, setSize, expanded, selected, pageId, ownedGroupId, labelId})`;
  call them from both `renderTreeNodes()` and `_buildRowHtml()` so root, recent, lazy,
  paginated, and live-inserted rows cannot drift in ARIA shape.
  Each row’s `aria-labelledby` targets the visible name or pagination-action element,
  while group and label IDs use the same safe deterministic encoder.
- Extend `renderTreeNodes(nodes, isRoot, options)` with `options.level`,
  `options.positionOffset`, and `options.setSize`; emit ID-bearing `role="group"`
  containers owned through each folder’s `aria-owns`, and emit pagination as a treeitem
  with a generated identity, level, position, and set size.
  Preserve the position offset in `pendingTreePages` so newly mounted batches continue
  the branch numbering.
- Add `treeRootForPanel(panel)` and `treeLevelForContainer(container)`. Update
  `_findChildContainerFor()` and root insertion selectors for the new wrapper instead of
  adding one-off descendant selectors.
- Extract the delegated click body into `setFolderExpanded(row, expanded)`,
  `toggleTreeFolder(row, {recursive})`, `mountNextTreePage(row)`, and
  `activateTreeRow(row)`. Pointer clicks and navigator callbacks call these same
  functions; folder state updates class, display, and `aria-expanded` together.
  Pagination activation returns the first newly mounted row so synchronization keeps
  focus on newly revealed content instead of jumping backward.
  Expansion is a no-op for a known-empty folder, which remains an ARIA end node.
- Route every repair through exactly two helpers so no call site reaches
  `treeKeyboard.synchronize()` directly.
  `synchronizeTreeNow()` repairs in the current turn and cancels any queued pass;
  `scheduleTreeSynchronize(snapshot)` coalesces a burst into one pass on the next task
  and keeps the earliest pending focus snapshot, which is the one describing the tree as
  the user last saw it.
- Use `synchronizeTreeNow()` for the paths a person just triggered:
  `renderFilesFromTree()`, `renderRecentFromBase()`, `loadSubtree()`, pagination, folder
  expansion or collapse, and `revealInTree()`.
- Use `scheduleTreeSynchronize()` for the paths the inventory stream drives:
  `applyCellPatch()`, `_insertRowSorted()`, `_synchronizeDeferredTreePage()`, animated
  removal, and both exits of `applyTreeFilters()`. A reconnect replays a whole snapshot
  through `applyCellPatch()`, so an immediate repair per entry would walk the painted
  tree once per file. Callers that need the repair in their own turn follow
  `applyTreeFilters()` with `synchronizeTreeNow()`, which supersedes the queued pass
  rather than adding a walk.
- Recursive expand and collapse both pass `{synchronize: false}` down the walk,
  including the lazy-load continuation inside `setFolderExpanded()`, so the walk itself
  costs one repair rather than one per descendant folder.
  A lazily loaded subtree still repairs around its own fetch, because its placeholder
  and then its loaded rows each change the visible order.
- Call `treeKeyboard.prepareForMutation()` before replacement or removal, and
  `treeKeyboard.setSelectedPath(path)` from `setSelectedPath()` so `.selected` and
  `aria-selected` change in one application turn.
- Pass the shared registry and overlay factory into `MetabrowserSearchPalette.create()`.
  `initQuickFileFinder()` otherwise keeps the current catalog, search-provider,
  revalidation, and navigation wiring.

No listener or callback is added to `.preview-pane`; native arrows, Home, End, Page Up,
Page Down, and Space therefore remain unhandled.

#### `server.py`, `types.d.ts`, and `styles.css`

`server.py:index()` adds cache-busted URLs for `keyboard_shortcuts.js`,
`overlay_layer.js`, `keyboard_help.js`, and `tree_keyboard_navigation.js`. It emits them
in that dependency order before `search_palette.js` and `app.js`. The template adds an
empty `#nav-shortcut-hints` region immediately before `#index-progress`; the progress
live region remains unchanged.
The hints region carries `role="group"` together with its accessible name, because ARIA
forbids naming a generic element and a bare `div` would drop the label.

`static/types.d.ts` declares the internal registry, presentation snapshot, modal, Help,
and tree-navigator globals used across strict modules.
None is added to `window.metabrowser` or the plugin SDK types.

`static/styles.css` adds shared `.modal-overlay`, `.dialog`, `.dialog-header`,
`.dialog-title`, `.dialog-close`, `.dialog-body`, and `.dialog-footer` primitives; Quick
File selectors become consumer modifiers of those primitives.
It also adds token-only Help, nav-hint, and `.tree-item:focus-visible` rules, responsive
wrapping, bounded dialog scrolling, and reduced-motion behavior.
New selectors introduce no literal colors, shadows, radii, z-indexes, or type sizes.

#### Test and Distribution Files

- `tests/dom/keyboard_shortcuts_behavior.js` covers validation, matching, priority,
  editable and composition guards, repeat policy, invocation, single-command and
  snapshot presentation, subscription, and disposal.
- `tests/dom/overlay_layer_behavior.js` covers modal arbitration, anatomy, inert-state
  restoration, control binding and trigger-state restoration, Tab containment, every
  close path through one descriptor, detached-focus fallback, registry scope disposal,
  and portal cleanup.
- `tests/dom/keyboard_help_behavior.js` covers exact copy, safe project link, Help
  groups, keyed persistent and contextual hints, trigger preservation, pointer
  invocation, valid-or-omitted ARIA, and subscription disposal.
- `tests/dom/tree_keyboard_navigation_behavior.js` covers every tree key, visible-order
  rules, concise accessible names, owned group relationships, declared level and set
  metadata, focus versus selection, known-empty end nodes, pagination, lazy children,
  render repair, scope activation, and native unhandled keys.
- `tests/dom/search_palette_behavior.js` replaces local-key and local-overlay assertions
  with injected registry and modal assertions while retaining every search, stale-row,
  catalog-growth, cancellation, and result-opening regression.
- `tests/test_browser_keyboard_js.py` runs the four new Node behavior suites under the
  existing subprocess convention.
- `tests/test_quick_file_integration.py` asserts the full script dependency order, one
  document dispatcher, injected palette dependencies, and absence of Quick File’s old
  global listener and hint table.
- `tests/test_browser_recent_ui.py` asserts the hint host is immediately above progress,
  the progress region remains polite, and navigable content has one dedicated tree
  wrapper.
- `tests/test_browser_filter_ui.py` and `tests/test_browser_v2.py` update structural
  expectations affected by the tree wrapper and assert synchronization at each render
  path.
- `devtools/check_distribution.py` requires all four new static modules in the wheel;
  the isolated-wheel smoke test confirms they are importlib resources.
- `README.md` adds `?` Help, the persistent hint strip, and tree navigation to the
  existing Quick File section after behavior is implemented.
  `CHANGELOG.md` records the same user-visible behavior under Unreleased without listing
  internal modules.

### Dependency Order

1. Land the registry, group definitions, formatter, renderer, and behavior tests.
2. Land the modal slice of the overlay layer against the registry.
3. Build Help and the persistent hint strip; migrate Quick File in parallel with the
   pure tree navigator once their shared prerequisites exist.
4. Integrate tree semantics and synchronization through every `app.js` render path.
5. Run cross-surface DOM, HTML, distribution, and real-browser validation; update the
   README and pass `make verify`.

### API Changes

There are no HTTP, Python, command-line, persistence, or public plugin API changes.
The new `window.Metabrowser*` factories are internal script-composition seams like the
existing search modules.
They are not added to `window.metabrowser` and carry no compatibility promise for
plugins.

## Implementation Plan

### Phase 1: Registry, Help, and Shared Hints

- [x] Write failing Node DOM tests for shortcut matching, scope precedence, editable
  guards, duplicate detection, descriptor-copy validation, handled-event semantics,
  subscriptions, and disposal
- [x] Write binding-presentation contract tests for every canonical key, alternative and
  future-chord grammar, spoken names, valid and deliberately omitted ARIA serialization,
  and identical rendering across Help, nav, Quick File, and menu hints
- [x] Implement the strict shortcut registry, binding formatter and renderer, ordered
  group registry, and one document dispatcher
- [x] Reuse or extract the shared modal slice specified by the menu and overlay plan,
  integrating Escape through the shortcut registry and adding inert-background restore
- [x] Implement the Help dialog with the approved description, GitHub link, generated
  shortcut groups, shared dialog anatomy, focus restoration, and disposal
- [x] Add the persistent nav hint host above index progress and render Help and Quick
  File from registry data
- [x] Migrate Quick File open keys, modal scope, Escape, result-navigation commands, and
  hint rows through the same dialog, registry, and binding primitives without changing
  its search behavior
- [x] Add static-asset ordering and package-data checks for every new module
- [x] Review the finished markup, copy, styles, and tests against every applicable
  [design-system](../../../design-system.md) keyboard, Help, overlay, and accessibility
  rule; do not accept local exceptions without documenting them there

### Phase 2: Tree Keyboard Navigation

- [x] Write failing DOM tests for ARIA structure, roving focus, each tree key, focus
  versus selection, and unhandled preview/editable keys
- [x] Add semantic root, group, tree-item, expanded, selected, level, and tabindex
  attributes to root, recent, lazy, paged, and live-update rendering paths
- [x] Implement synchronized visible-row navigation and existing-action callbacks
- [x] Preserve or repair the roving anchor across filtering, source replacement, lazy
  loads, pagination, insertion, removal, and type replacement
- [x] Add focus-visible styling and contextual tree hints from the registry
- [x] Validate pointer behavior, keyboard behavior, narrow navigation panes, light and
  dark themes, 200% zoom, reduced motion, and screen-reader naming in a real browser
- [x] Run `make verify` as the required handoff gate

## Testing Strategy

### Shortcut Registry

- exact matching for `?`, `/`, unmodified `t`, and Caps Lock `T`;
- Shift+T and Ctrl/Alt/Meta variants remain untouched;
- composition, editable targets, and already-prevented events remain untouched;
- modal scope wins over tree scope, which wins over global scope;
- repeat is accepted for tree movement and rejected for open/toggle commands;
- duplicate bindings in one scope fail deterministically;
- unknown semantic keys and Help or hint descriptors with incomplete copy fail
  deterministically;
- an unhandled command does not prevent browser behavior;
- registrations, subscriptions, active scopes, and the document listener dispose;
- every canonical key has the specified visible and spoken form plus the correct valid
  or omitted ARIA form; and
- alternatives render with “or,” while a chord renders with “plus” in its spoken form.

### Help and Hints

- Help opens from both `?` and the visible button, mounts once, and restores focus;
- title, shared dialog anatomy, modal semantics, inert background, approved description,
  GitHub URL, new-tab description, link safety attributes, and Close control are
  present;
- Help rows and nav hints are derived from registry snapshots;
- Help, nav, Quick File, and menu-hint sample bindings produce the same canonical `.kbd`
  structure and spoken phrase;
- shortcut controls receive formatter-derived `aria-keyshortcuts` only for accurately
  representable physical bindings while retaining their action label as the accessible
  name;
- tree hints appear on tree focus and disappear when focus leaves;
- hint updates are not live-announced, while index progress remains polite;
- compact hints use descriptor copy without key-name repetition or slash-as-“or”
  abbreviations; and
- narrow widths and 200% zoom wrap without covering the Close control or progress text.

### Overlay Integration

- the registry remains the only document-level application-shortcut dispatcher;
- Escape closes the topmost anchored popup before its containing modal;
- Escape, Close, and scrim paths restore focus and remove scope registrations;
- disposal restores pre-existing trigger and inert state and leaves no portal, scrim,
  listener, observer, or registration; and
- light and dark surfaces use shared semantic tokens, and reduced motion does not change
  content, focus order, or dismissal behavior.

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
- The registry and its group descriptors are the only source for commands, context, and
  copy shown in Help or hints
- One formatter and renderer supply every visible key name, binding separator, spoken
  phrase, and valid-or-omitted `aria-keyshortcuts` decision; no surface-specific
  abbreviation map remains
- Help and Quick File use the shared dialog anatomy, semantic tokens, modal focus,
  inert-background, Escape, and disposal contracts; no Help-only overlay lifecycle
  exists
- Every visible tree row is keyboard reachable through one roving Tab stop
- Folder, leaf, lazy, paginated, filtered, recent, and live-update rows preserve the
  specified keyboard and focus behavior
- Main-pane arrows and scrolling keys retain native browser behavior
- Quick File retains its current functionality and no global shortcut fires in editable
  content
- Help, hints, and popups satisfy the design-system copy and overlay review at narrow
  width, 200% zoom, light and dark themes, reduced motion, and keyboard-only operation
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

- [Quick File finder and search providers](../active/plan-2026-07-17-scalable-file-search.md)
- [Menu primitives and gated file actions](../active/plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Filter controls and fine-grained navigation filtering](../active/plan-2026-08-09-nav-filter-controls.md)
- [Design system](../../../design-system.md)
- [End-to-end testing](../../../e2e-testing.md)
- [Metabrowser on GitHub](https://github.com/jlevy/metabrowser)
- [WAI-ARIA Authoring Practices tree view pattern](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
