# Feature: Menu Primitives and Gated File Actions

**Date:** 2026-08-06 (last updated 2026-08-06)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser has a menu *look* but not a menu *behavior layer*. The settings gear is the
only menu in the app, and everything that makes it a menu — opening, anchoring,
dismissal, focus — is hand-written inline in `app.js` against one fixed position in the
header.

This plan adds the missing behavior primitives so a menu can be opened anywhere, from
any trigger, over any anchor, with one keyboard and dismissal contract; adds an in-place
text edit primitive; and lands the first consumer: right-click a file in the nav tree to
rename it inline or move it to trash, behind a mutation capability that is off unless
the server was started with explicit authorization.

The component work is the point.
Rename and trash are the proof that the vocabulary is real, not the reason to build it.

## Goals

- Extract one anchored-overlay primitive that owns positioning, viewport containment,
  dismissal, focus save and restore, and disposal
- Extract one modal-dialog shell and make the existing Quick File palette its first
  consumer, so the app has exactly one modal implementation
- Add a data-driven action menu that renders the existing `.menu` and `.menu-item` CSS
  from an action list rather than from hand-written markup
- Add an action registry so a menu’s contents are resolved from a context (what was
  clicked, which capabilities are live) instead of hard-coded per call site
- Add an in-place edit primitive with commit, cancel, validation, and rollback
- Add a context menu on nav-tree rows, opened by right-click and by the keyboard, which
  requires giving tree rows a minimal keyboard focus order they lack today
- Add file rename and trash behind a `POST /api/mutate` capability gated at server
  startup
- Keep every new browser module under the strict `tsconfig.json` gate and under
  Node-driven DOM tests

## Non-Goals

- In-browser text editing, save proposals, or drafts — those belong to the
  [editor plugin editing contract](../../architecture/arch-editor-plugin-editing-contract.md)
- Plugin-contributed actions and plugin-defined mutations; the registry is designed so
  the SDK can expose it later, but the SDK surface is not part of this plan
- Submenus, cascading menus, and menu bars
- Menu typeahead and mnemonics — a two-to-five-row menu does not earn the
  buffer-and-timeout state; revisit if a menu grows past a dozen rows
- Directory rename and trash — deferred until the recursive inventory-reconciliation
  cost is measured on a large tree; the registry’s `appliesTo` makes the extension a
  descriptor change, not a redesign
- OS-level trash integration (`send2trash`) — rejected for now in favor of the
  quarantine design below; the quarantine layout leaves room to add it later
- The full ARIA tree role model (`role="tree"`, `aria-expanded`, `aria-level`) for the
  nav pane — this plan adds row focusability and a focus order, not complete tree
  semantics
- Drag-and-drop move, multi-select, and bulk operations
- Copy, duplicate, new file, and new folder — the registry makes them cheap to add, but
  each needs its own conflict semantics
- Permanent deletion
- Remote, public, or multi-tenant editing

## Background

### What the design system already provides

Metabrowser’s design system is strong at the token and surface layer.
`static/styles.css` defines layered tokens, and the ones relevant here are already in
place:

- a named z-index scale — `--z-pane`, `--z-resize-handle`, `--z-overlay` for anchored
  menus, `--z-modal` for blocking dialogs, `--z-tooltip` on top;
- floating-surface tokens — `--viz-surface-raised`, `--viz-border-strong`,
  `--radius-chrome`, `--shadow-lg`, `--modal-scrim`;
- semantic status colors including `--status-error` for destructive affordances;
- the type scale, with `--ui-small-font-size` for menu text and `--nav-font-size` for
  tree rows.

`styles.css` also defines a documented `.menu` primitive: the surface itself, plus four
content primitives inside it — `.menu-item` (icon slot and label, with `[aria-disabled]`
and `[aria-checked]` states), `.menu-chooser` and `.menu-seg` (a segmented control),
`.menu-select`, and `.menu-separator`. Its comment block already states the intent: “any
future menu renders the same markup so every menu reads identically.”

The `.icon-btn` primitive covers the trigger side.
Every menu opener is an icon button, and that primitive already treats hover, keyboard
focus, and “my menu is open” as one visual state — so a generic opener needs no new CSS,
only something to drive that state.
`.kbd` covers keyboard hints inside a menu row.

### What is missing

The intent is documented; the mechanism is not built.

**The `.menu` primitive has one consumer, and `.menu-item` has zero.** The settings gear
in the index template uses `.menu` with two `.menu-chooser` rows and a `.menu-select`.
The vertical-list row — the primitive an action menu is made of — is styled but has
never been rendered by anything.

**Positioning is CSS, not code.** `.settings-toggle .settings-menu` is
`position: absolute; top: calc(100% + 4px); right: 0`, which works only because the
trigger is pinned to a corner and the menu can never overflow.
There is no anchoring logic, so there is no way to open a menu at a pointer coordinate,
and no way to flip or clamp a menu that would fall off the viewport edge.

**Behavior is inline and single-purpose.** `initSettingsControl()` in `app.js` toggles
an `aria-expanded` attribute on a wrapper and installs its own document-level click and
Escape listeners. They are never removed, they are not shared, and a second menu built
the same way would open on top of the first with no arbitration.

**There is no keyboard model for a menu.** The gear’s segments are reached by Tab.
Nothing in the app implements arrow-key roving focus, Home and End, or
`Escape`-returns-focus-to-trigger over a vertical list.

**Tree rows cannot take keyboard focus.** `renderTreeNodes` emits rows with no
`tabindex`, so no row is reachable by keyboard at all — selection is mouse-only today,
and a menu “opened on the focused row” has nothing to anchor to.
The design-system accessibility checklist already promises keyboard operability, so a
row-targeted menu cannot ship without closing at least the focus-order slice of this
gap.

**The two behaviors we do have are trapped inside their features.** The custom tooltip
(`app.js`) has the app’s only viewport-clamping logic, and it is private to
`positionTooltip`. The Quick File palette (`static/search_palette.js`) has the app’s
only correct overlay lifecycle — body-portaled surface, scrim, `role="dialog"` with
`aria-modal`, focus captured on open and restored on close, Escape and
outside-pointerdown dismissal, a real `dispose()`, injected `document` for testing, and
a frozen public API. That is exactly the contract a menu needs, and none of it is
reusable.

**There is no command model.** Menu contents are literal markup in `server.py`’s index
template. A context menu needs the opposite: a list of actions resolved at open time
against what was clicked and what the server permits.

**There is no in-place edit.** Nav rows are innerHTML-rendered strings; nothing in the
app swaps a label for an input, and nothing owns commit, cancel, validation, or
rollback.

**There is no mutation plane.** Every route is read-only except
`POST /api/kpress/export`. There is no `--allow-edits` gate, no mutation service, and
`client_settings_dict()` publishes no capability flags.
The [trusted-local file editing plan](plan-2026-07-16-trusted-local-file-editing.md)
defines the umbrella policy; this plan lands its rename-and-trash slice together with
the menu vocabulary that policy assumed but never specified.

### The organizing principle

The gap is not “we need a context menu.”
It is that the design system stops at the surface layer.
This plan adds the three layers above it and keeps them separate, so each is
independently testable and reusable:

| Layer | Owns | Today |
| --- | --- | --- |
| Surface | Tokens, `.menu`, `.menu-item`, `.icon-btn`, `.kbd`, scrim, z-scale | In place; no plain text button yet (Phase 2 adds one for dialogs) |
| Placement | Anchoring, flip and clamp, dismissal, focus, disposal | Absent; partially duplicated in tooltip and palette |
| Content | Rendering a list into a surface, keyboard model, ARIA roles | Absent |
| Command | What actions exist, when they are enabled, what they do | Absent |

Keeping placement separate from content is what makes “a menu in any location” true: the
same placement primitive serves a right-click menu, a button dropdown, a future overflow
menu, and eventually the tooltip, because none of them differ in how they are placed —
only in what they contain.

## Design

### Approach

Build the placement and content primitives first, port the two existing floating
surfaces onto them so there is one implementation of each behavior, then add the command
layer and the tree context menu, then add the server mutation plane and wire rename and
trash as the first two actions.

Every new browser module follows the shape `search_palette.js` established, because that
shape is already proven under the strict TypeScript gate and Node DOM tests: an IIFE
exposing a frozen factory on `window.Metabrowser*`, an injectable `document`, and a
`dispose()` that removes every listener and DOM node it created.

### Components

#### Browser: `static/overlay_layer.js` → `window.MetabrowserOverlay`

The placement primitive.
One factory that takes content and an anchor and returns a controller.

Anchors are a tagged union so a pointer coordinate and an element are the same kind of
thing to the caller:

- `{kind: "point", x, y}` — right-click;
- `{kind: "element", element, placement}` — trigger buttons, where `placement` is a
  preferred side and alignment.

Placement resolves the preferred position, then flips to the opposite side and clamps to
the viewport with a margin when the surface would overflow — the same rule
`positionTooltip` applies today, promoted out of the tooltip and made the single
implementation. A surface taller than the viewport gets a max-height and scrolls
internally.

Every surface portals to `document.body` and positions in viewport coordinates.
That is a correctness requirement, not a style choice: `.preview-pane` carries
`transform: translateZ(0)` (its KPress containment fix), and a transformed ancestor
becomes the containing block for `position: fixed` descendants, so a menu mounted inside
a pane would pin to the pane instead of the viewport.
The body portal also means a tree re-render or preview replacement cannot detach an open
surface.

The controller owns the anchored dismissal contract — Escape, `pointerdown` outside the
surface, scroll and resize outside the surface, and window blur all close it — with two
guarantees that name classic bugs: the interaction that opened a surface can never
dismiss it in the same event sequence, and scrolling *inside* a scrollable surface never
dismisses it. It also owns focus save on open and restore on close, with a re-resolve
fallback when the saved element is no longer connected (tree rows are innerHTML-rebuilt
under live events), and the trigger contract: `aria-expanded` and `aria-haspopup="menu"`
maintained on an optional trigger element — exactly the state the `.icon-btn` open style
keys off.

Arbitration is deliberately minimal, not a stack: at most one anchored overlay and one
modal at a time; opening an anchored overlay closes any other anchored overlay and
leaves a modal alone.
One module-owned document `keydown` listener routes Escape to the topmost open surface,
replacing the palette’s and the settings menu’s private, never-removed document
listeners rather than becoming a third.

The same module exposes a modal variant: scrim at `--z-modal`, `role="dialog"` with
`aria-modal="true"`, focus capture and restore, and a minimal Tab wrap over the dialog’s
focusable descendants that a consumer may override — the palette keeps its stricter
input-pinned Tab behavior.
`search_palette.js` is ported onto it in the same phase, so the app keeps exactly one
modal implementation and the palette’s tested behavior becomes the shared behavior
rather than a second copy.
Modals do not dismiss on scroll, resize, or blur; only Escape, an explicit control, or
scrim `pointerdown` closes them, matching the palette today.

#### Browser: `static/action_menu.js` → `window.MetabrowserMenu`

The content primitive.
Renders a resolved action list into `.menu` markup — `.menu-item` rows with
`.menu-item-icon` and `.menu-item-label` slots, `.menu-separator` between groups — and
mounts it through `MetabrowserOverlay`. This is the first real use site for
`.menu-item`.

It owns the keyboard model: `ArrowDown` and `ArrowUp` with wrap, `Home` and `End`,
`Enter` and `Space` to invoke, and `Escape` to close and return focus to the trigger.
Pointer hover and keyboard roving drive one shared active state, the way the palette’s
option list already works.
`role="menu"` and `role="menuitem"` are set here, not by callers.

Disabled rows carry `aria-disabled="true"` and stay **focusable** — the ARIA menu
pattern recommends it, and it is what makes a disabled reason discoverable from the
keyboard — but never invocable.
The reason renders as the row’s `title` and as a visually-hidden description announced
on focus.

Invocation order is part of the contract: the menu closes and restores focus *first*,
then the action runs.
Rename swaps a row label for an input and focuses it; a menu that restored focus after
running the action would steal focus back from the editor the action just opened.

Labels are written as text nodes, never as innerHTML — the same discipline
`appendHighlightedText` follows in the palette — because action labels will eventually
carry filenames. Icons are the only markup accepted, and only from the `ICONS` registry.

Two CSS additions are needed, both consuming existing tokens: `.menu-item.destructive`
using `--status-error` for the label and icon, and a `.menu-item-hint` slot on the
trailing edge for a keyboard shortcut rendered with the existing `.kbd` component.

#### Browser: `static/action_registry.js` → `window.MetabrowserActions`

The command primitive.
An action is a plain descriptor:

```js
{
  id: "file.rename",
  label: "Rename…",
  icon: "pencil",
  group: "edit",
  destructive: false,
  appliesTo: (ctx) => ctx.kind === "file" || ctx.kind === "dir",
  isEnabled: (ctx) => ctx.capabilities.mutations,
  disabledReason: (ctx) => "Editing requires starting the server with --allow-edits",
  run: (ctx) => { /* … */ },
}
```

A context is what was clicked plus what is permitted:
`{kind, path, name, capabilities, element}`. The `path` is the durable identity; the
`element` is a hint an action must re-resolve at run time, because tree rows are
innerHTML-rebuilt and the row that opened the menu may be a detached node by the time
the action runs. Resolving a registry against a context yields the ordered, grouped,
enabled-or-disabled list the menu renders; a context with no applicable actions opens no
menu at all and lets the browser’s native menu through.

Actions that require a capability stay **visible and disabled with a reason** rather
than hidden, so a read-only server explains itself instead of silently offering less.
The client capability flag is a presentation hint only; the server re-checks on every
request.

The registry resolves and orders; it owns no progress or error UI. Each action drives
its own surface — rename the inline editor, trash the confirmation dialog — which keeps
the command layer thin.
The same descriptors also serve entry points that are not menus: Phase 2 binds `F2` and
`Delete` on the focused tree row to the same rename and trash actions, which is the
content/command separation earning its keep.

#### Browser: `static/inline_edit.js` → `window.MetabrowserInlineEdit`

The in-place edit primitive.
Given a target element, it replaces the element’s text with an input styled to sit
exactly where the label was — `--nav-font-size`, `--font-sans`, so the row does not
reflow — and returns a promise-shaped controller.

It owns: initial selection (for a filename, the stem is selected and the extension is
not, matching VS Code), `Enter` to commit, `Escape` to cancel, commit on blur, a
synchronous local validator, an inline error state that keeps the input open on
rejection, a pending state while an async commit is in flight, and restoration of the
original element on cancel, failure, or disposal.
Cancelling marks the session before focus moves, so the blur that `Escape` itself
triggers cannot turn the cancel into a commit — that ordering is a named test, not an
implementation accident.

Because tree rows are re-rendered from innerHTML by live filesystem events, the
controller registers the edited path and, when a re-render replaces its row, re-mounts
the editor onto the new row element with value, caret, and pending state carried over.
If the re-render removed the row entirely — the file vanished externally — the editor
closes with a status instead of committing into nothing.

#### Browser: tree integration in `app.js`

One `contextmenu` listener delegated on `#tree-pane`, matching the existing click
delegation pattern. The browser fires `contextmenu` for right-click and for the keyboard
(`Shift+F10` and the Menu key) alike, so a single handler serves both; when the event
carries no usable pointer coordinates, the menu anchors to the row element instead of
the point. An event that does not land on a row is left alone, so the browser’s own menu
still works over empty space.

Right-click does **not** change the selection: selecting a file loads its preview, and
opening a menu must not trigger a fetch.
The context comes from the row’s existing `data-path`, `data-tip-type`, and
`data-tip-name` attributes, and the row shows a menu-open target state (the existing
hover surface) while its menu is up, so the target is visible without being selected.

Keyboard reach is the prerequisite half of this integration: tree rows join a minimal
roving-tabindex focus order — `ArrowUp`, `ArrowDown`, `Home`, `End` over the rendered
rows, `Enter` mirroring click — scoped to rendered rows only.
That is the smallest change that makes “open the menu on the focused row” true for a
keyboard user; the full ARIA tree role model stays out (see Non-Goals).

#### Server: `src/metabrowser/mutations.py`

The mutation service, operating on regular files only in this plan.
It re-resolves the source through the existing `paths_safe` helpers immediately before
acting, verifies containment within the served root after symlink resolution, verifies
the target is a regular file, validates the proposed name (non-empty, no path
separators, no `.` or `..`, no NUL, reserved names rejected), rejects an existing
destination rather than overwriting, and returns a structured outcome for every failure
with the exception cause preserved.

Trash is a served-root-local quarantine, decided here rather than left open: the file
moves to `.metabrowser-trash/<timestamp>-<serial>/<relative-path>` inside the served
root, and the directory is registered with the ignore filter so it never appears in the
tree, the inventory, or the Quick File catalog.
The UI says “moved to Metabrowser trash” — never “Trash”, because it is not the OS
trash. This costs no new dependency (`send2trash` would sit behind the supply-chain
cool-off), behaves identically on every platform, keeps every mutation inside the
containment boundary, and is recoverable by hand until an undo affordance exists.
The `<serial>` suffix makes two same-second trashes of one name collision-proof.
A move the OS refuses — a bind-mount boundary, a permission wall — surfaces as a
structured failure, never a silent copy-and-delete fallback.

On success it invalidates and republishes through the existing inventory event path
(`invalidate`, `remove`, `apply_live_entry`, `emit_event`) so open views reconcile
through the same route an external filesystem change takes.
Two client behaviors close the loop for the previewed file: renaming it re-targets the
open preview to the new path, and trashing it leaves the preview in an explicit removed
state rather than an error wall.

#### Server: capability gate

`--allow-edits` on `metab serve`, or `METAB_ALLOW_EDITS=1`, resolved before app
construction and off by default.
The resolved value is published to the client through `client_settings_dict()` as a
`CAPABILITIES` block, keeping the existing “one dict, no duplicated constants”
convention. When editing is enabled, the header shows a persistent, non-dismissible
edit-mode badge.

### API Changes

One route, one tagged operation union, so later operations — including the editor
contract’s `replace_text` — extend the same envelope instead of adding sibling routes.
This answers that document’s open question about the final mutation route.

| Interface | Method | Description |
| --- | --- | --- |
| `/api/mutate` | POST | Apply one bounded mutation operation |

Requests carry only served-root-relative paths.
No request accepts a client-supplied absolute path, and rename accepts a bare name
rather than a destination path, so the first operation cannot express a move at all:

```json
{"operation": "rename", "path": "notes/draft.md", "new_name": "final.md"}
{"operation": "trash", "path": "notes/draft.md"}
```

Success returns the outcome, the operation, and only paths the interface may display; a
trash success additionally reports `trashed_to`, so the status line can say where the
file went:

```json
{"outcome": "ok", "operation": "rename", "path": "notes/final.md", "previous_path": "notes/draft.md"}
```

Failures return a stable code, an HTTP status, and a human-readable message:
`edits_disabled` (403), `invalid_name` (400), `invalid_path` (400), `not_found` (404),
`name_conflict` (409), `stale_revision` (409), `permission_denied` (403), and `io_error`
(500) for an operating-system refusal, with the cause preserved server-side.

`expected_revision` is an **optional** guard on rename and trash: when the client
supplies one — derived from the stat identity the tree rows already carry — and it no
longer matches, the server answers `stale_revision` instead of acting.
Keeping it optional here avoids building token-issuance plumbing that rename and trash
do not need for safety (re-resolution, no-overwrite, and a recoverable trash carry
that), while future content-writing operations such as the editor contract’s
`replace_text` will require it on the same envelope.
It is distinct from the inventory’s internal `WriteToken`, which is a generation counter
for producer race-safety and is never client-visible.

When editing is disabled the route exists and returns a stable `edits_disabled` response
rather than 404, so the client can distinguish “not permitted” from “not deployed”.

A mutation route on a loopback server needs cross-site protection that read routes do
not: any web page in another tab can *send* a POST to `127.0.0.1` — the browser blocks
reading the response, not sending the request.
The route therefore rejects requests whose `Content-Type` is not `application/json` (a
cross-origin page cannot set that header without a CORS preflight the server never
grants) and rejects requests carrying a `Sec-Fetch-Site` header other than `same-origin`
or `none`. Together with the existing host-validation middleware this closes the
drive-by-write path.

## Implementation Plan

### Phase 1: Overlay, Menu, and Command Primitives

- [ ] Add `overlay_layer.js` with point and element anchoring, flip-and-clamp
  containment, the anchored dismissal contract, focus save and restore with the
  detached-element fallback, the shared Escape router, single-open arbitration, and
  disposal
- [ ] Add the modal variant and port `search_palette.js` onto it, deleting the palette’s
  private overlay, scrim, focus, and dismissal code (sequence this after the in-flight
  quick-file palette branch lands, so the port rebases once, not continuously)
- [ ] Move `positionTooltip`’s clamping onto the shared placement helper
- [ ] Add `action_menu.js` with the roving-focus keyboard model, focusable disabled
  rows, ARIA roles, text-node labels, and grouping
- [ ] Add the menu and edit CSS from existing tokens: `.menu-item.destructive`,
  `.menu-item-hint`, the inline-edit input class, and the row menu-open target state
- [ ] Add `action_registry.js` with context resolution and capability-aware enablement
- [ ] Add `inline_edit.js` with selection, commit, cancel, validation, pending, error,
  re-mount across re-renders, and restore
- [ ] Give tree rows the minimal roving-tabindex focus order — arrow keys over rendered
  rows, `Enter` mirroring click — so the focused row is a real menu target
- [ ] Wire the one nav-tree `contextmenu` handler for pointer and keyboard, registering
  the real rename and trash descriptors; with no `CAPABILITIES` published yet they
  render disabled with their reasons, which is the Phase 1 deliverable
- [ ] Port the settings gear onto the shared overlay, moving `aria-expanded` onto the
  trigger button and deleting the scoped `display` CSS and the gear’s private document
  listeners
- [ ] Add Node DOM tests for each module and register them under `tests/`
- [ ] Add a “Menus, Overlays, and In-Place Editing” section to the
  [design system](../../../design-system.md), alongside the icon-button section, so the
  placement, content, and command layers are documented where the surface layer already
  is

### Phase 2: Gated Rename and Trash

- [ ] Add the `--allow-edits` and `METAB_ALLOW_EDITS` gate, the `CAPABILITIES` block in
  `client_settings_dict()`, and the persistent edit-mode badge
- [ ] Add `mutations.py` with name validation, containment re-resolution, optional
  revision guards, quarantine trash, conflict detection, and structured outcomes
- [ ] Add `POST /api/mutate` with the rename and trash operations and the content-type
  and `Sec-Fetch-Site` cross-site checks
- [ ] Publish successful mutations through the inventory event path; re-target the
  preview when the open file is renamed and show an explicit removed state when it is
  trashed
- [ ] Add the first text-button pair (`.btn`, `.btn.destructive`) to `styles.css` for
  the confirmation dialog — the app has icon, tab, and filter buttons but no plain text
  button today
- [ ] Wire rename to `inline_edit.js` and trash to a confirmation on the shared modal
  shell, and bind `F2` and `Delete` on the focused tree row to the same descriptors,
  hints rendered through `.menu-item-hint`
- [ ] Document the capability, the quarantine trash semantics, and the trusted-local
  warning

## Testing Strategy

Browser primitives are tested the way `search_palette_behavior.js` already is — Node
scripts driving an injected document, run from a thin pytest wrapper:

- placement: preferred position honored, flip on each edge, clamp in a corner,
  max-height with internal scroll, point and element anchors;
- dismissal and lifecycle: Escape, outside pointerdown, scroll, resize, and blur close
  an anchored surface; the opening interaction never dismisses its own surface;
  scrolling inside a scrollable surface does not dismiss it; a second open closes the
  first; an anchored overlay leaves a modal alone; focus returns to the trigger, with
  the detached-trigger fallback; `dispose()` leaves no listeners or nodes;
- keyboard: arrow wrap, Home and End, disabled rows focusable, announced with their
  reason, and never invocable; invoking closes the menu and restores focus *before* the
  action runs; Escape returns focus;
- registry: enablement and disabled reasons under both capability states, grouping and
  separator placement, and the empty-context path that opens no menu;
- inline edit: stem-only preselection, commit, cancel, Escape-then-blur does not commit,
  validator rejection keeps the editor open, async failure rolls the row back, a
  concurrent re-render re-mounts the editor with its state, a removed row closes it with
  a status;
- tree: right-click opens the menu without changing selection or fetching a preview, and
  an off-row right-click falls through to the native browser menu;
- the ported palette keeps its entire existing assertion set green, which is the proof
  the extraction did not regress it.

Server tests run only against isolated temporary roots and cover: disabled startup
exposes no successful mutation; requests without `application/json` or with a cross-site
`Sec-Fetch-Site` are rejected; traversal, symlink escape, and time-of-check/time-of-use
races; destination collision never overwrites; a supplied stale revision conflicts;
missing parents; permission and OS failures surfacing as structured outcomes with causes
preserved; and quarantine containment, ignore-filter coverage, and collision-proof
naming. A real-browser test covers right-click through committed rename, with the tree
and preview reconciling from the event stream and no restart.

## Rollout Plan

Phase 1 ships as pure refactor plus new primitives with no user-visible new capability
beyond a context menu whose entries are all disabled with reasons, so the placement and
keyboard behavior can be reviewed before any write path exists.

Phase 2 ships rename and trash off by default.
Enabling requires an explicit startup flag, and the running server says so visibly.
Documentation retains the trusted-local warning: Metabrowser is a local developer tool,
not a public-facing server, and loopback binding alone does not make mutation safe.

## Open Questions

- Does trash need a confirmation dialog at all, given the quarantine is recoverable —
  and once an undo affordance exists, should the confirmation drop away?
  Phase 2 ships with confirmation as the safe first behavior.
- Should the registry be exposed through `window.metabrowser` in a later phase, and if
  so does a plugin-contributed action need its own capability declaration in the
  manifest?
- When the nav pane grows the full ARIA tree role model (`role="tree"`, `aria-expanded`,
  `aria-level`), should it land with the unified-filtering work that already touches
  tree navigation, or on its own?

## Acceptance Criteria

- One module owns anchored placement, and the tooltip, the palette, and the new menu all
  route through it; no second implementation of flip-and-clamp, scrim, focus restore, or
  outside-dismissal remains in the codebase
- A menu can be opened at a pointer coordinate or anchored to any element, in any pane —
  including over the transformed preview pane — with one line at the call site and no
  new CSS
- The path from tree row to committed action works by keyboard alone: focus a row with
  the arrow keys, open its menu, rove, invoke — and the menu has closed and restored
  focus before the action runs, so rename’s editor keeps the focus it takes
- Every new browser module passes under the strict `tsconfig.json` gate without being
  added to the legacy allowlist, and each has Node DOM coverage
- Right-clicking a nav row on a read-only server shows the actions, disabled, with a
  reason — and changes no selection, loads no preview
- With editing enabled, rename edits in place in the tree and trash removes the row,
  both reconciling through the existing event path without a restart
- `POST /api/mutate` refuses non-JSON content types and cross-site requests
- Read-only startup exposes no working mutation path, and no mutation can read or write
  outside the served root through traversal, symlinks, races, or crafted names
- Conflicts never overwrite an existing target silently, and every trashed file is
  recoverable from the quarantine by hand
- `make verify` passes

## References

- [Design system](../../../design-system.md)
- [Core architecture](../../../architecture.md)
- [Trusted-local file editing](plan-2026-07-16-trusted-local-file-editing.md)
- [Editor plugin editing contract](../../architecture/arch-editor-plugin-editing-contract.md)
- [Supply-chain security](../../../../SUPPLY-CHAIN-SECURITY.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
