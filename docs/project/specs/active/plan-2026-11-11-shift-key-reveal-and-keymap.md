# Feature: Shift Key Reveal and a Systematic Keymap

**Date:** 2026-11-11 (last updated 2026-11-11)

**Author:** Metabrowser maintainers

**Status:** Draft

## Overview

Metabrowser has a well-built shortcut registry that almost nobody can discover.
It dispatches Help, Quick Search, the main tabs, and the tree and Pulls row keys, but
the view tabs, header buttons, and filters a reader uses all day have no keys at all,
and the only way to learn a key is to open Help.

This plan makes the whole interface keyboard-friendly through one gesture: **hold Shift,
and every control that has a key shows that key.** A small yellow keycap appears at the
inline end of each live target: `1` on the Files tab, `2` on the Commits tab, `3` on the
Pulls tab, `S` on a file’s Source tab, `M` on a folder’s Treemap tab.
The shortcut strip at the bottom of the navigation pane turns the same yellow and lists
more of the common keys.
Releasing Shift puts everything back.

Three rules make the gesture honest:

- **Shift never changes what a letter or digit key means.** `T` and Shift+`T` both open
  Quick Search; `1` and Shift+`1` both show the Files tab.
  Holding Shift to look and then pressing the key you see therefore works for every
  badge, and Help can write every key as a bare capital.
  Punctuation is the one honest exception: it matches the character typed, so `/` is
  Quick Search and Shift+`/`, which types `?`, is Help.
- **No shortcut uses Cmd, Ctrl, or Alt.** Every key is a single key with optional Shift.
  The registry rejects a binding that requires any other modifier, so the released ⌘1,
  ⌘2, and ⌘3 main tab bindings go, and the bare digits they already aliased remain.
- **Keys come from a systematic allocation**, checked by the build: a fixed digit for
  each navigation-pane tab, a letter from the label for every main-pane tab, and a
  convention or mnemonic letter for each command.
  A key is live only while its target is visible.

Applying the Shift rule also moves pull request stack navigation off ⇧J and ⇧K, which
collide with the row keys `J` and `K` once Shift stops mattering, to `N` and `P`.

Phase 1 covers the core shell.
Phase 2 opens a small `window.metabrowser.shortcuts` surface so built-in plugins can
register keys and badge targets, with the pull request page’s Conversation, Changes, and
Checks tabs and the diff layout toggle as its first consumers.

## Goals

- Reveal every live shortcut in place while Shift is held alone outside a text field,
  with no flash during ordinary Shift chords such as `?`, capitals, Shift+Arrow,
  Shift+wheel, and a Shift+click made while the pointer moves
- Make Shift irrelevant to every letter and digit shortcut, and match punctuation by the
  character produced
- Remove every Cmd binding and make the registry reject any binding that requires Ctrl,
  Alt, or Meta
- Move pull request stack navigation from ⇧J and ⇧K to `N` and `P`
- Assign keys by written allocation rules, record the assignments in one keymap, fail
  the build on a view or shell key collision, and refuse a colliding plugin key at
  registration
- Keep the main tabs’ fixed digits, give the main pane’s tabs a letter from their label,
  and give the common header and filter commands letters
- Turn the navigation-pane shortcut strip yellow while revealed and show the common keys
  there without reflowing or scrolling the navigation pane
- Write keys in Help as bare capitals, never with Shift, and end Help with the note
  “Press `Shift` to see relevant shortcut reminders.”
- Keep the registry the only document-level dispatcher, the formatter the only source of
  key names, and the design tokens the only source of color
- Keep the keymap and the reveal state machine pinned by browserless sessions and
  goldens, per [CLI and functional UI parity](../../../../AGENTS.md)

## Non-Goals

- User-customizable or persisted key bindings
- Multi-key sequences or a command palette
- Any binding with Ctrl, Alt, or Meta.
  In a browser those chords belong to the browser, which switches its own tabs on
  Cmd+digit or Ctrl+digit before a page sees the event; the unmerged macOS app spike’s
  menu equivalents, such as Cmd+0 for Actual Size, are native menu items and not
  registry bindings
- Changing Shift semantics of named navigation keys inside focused widgets: Shift+↑ and
  Shift+↓ in the file tree, Shift+Tab, and the line gutter’s Shift-extended selection
- Keys for every control.
  Rare controls such as the Metabrowser menu, the print button, retry, reload, and
  refresh buttons, the Pulls panel’s Open, Closed, and All chips, and per-file diff
  disclosures stay pointer- and Tab-reachable only in this plan
- Hint mode with generated two-letter labels on arbitrary links, as in browser
  extensions such as Vimium
- Plugin-defined key groups, or plugin keys outside a mounted plugin view
- Keeping an alias for a removed binding: ⌘1 through ⌘3 and ⇧J and ⇧K are removed, not
  shadowed, per the repository’s
  [compatibility rules](../../../development.md#compatibility-and-legacy-code)

## Background

### Today’s keys

`static/keyboard-shortcuts.js` is the single registry and dispatcher.
Its vocabulary is Space, `?`, `/`, the four arrows, Delete, End, Enter, Escape, F2,
Home, single letters, and digits `0` through `9`. The formatter renders the Meta
modifier as `⌘` and Shift as `⇧`.

Registered commands on `main`:

- **Anywhere:** Help (`?`) and Quick Search (`T` or `/`), the only two on the strip;
- **Main tabs:** `main-tabs.files`, `main-tabs.git`, and `main-tabs.pulls` in
  `static/main-tabs.js`, each bound to ⌘ plus its digit and to the bare digit, shown in
  Help only;
- **Navigation:** the file tree’s arrows, `J`, `K`, Home, End, Shift+↑, Shift+↓, Enter,
  and Space;
- **Pull requests:** the Pulls rows’ and changed-file rows’ arrows, `J`, `K`, Enter, and
  Space, in `static/pulls-nav.js`;
- **Pull request stack:** ⇧J toward the stack’s base and ⇧K toward its top, global while
  a pull request in a stack is open;
- **Quick Search** and **Help** modal commands.

The Git history rows handle `J` and `K` locally in `static/git-panel.js`.

The navigation pane has three tabs with fixed digits: **Files** `1`, **Commits** `2`,
and **Pulls** `3`. Commits appears once Git discovery finds a repository, and Pulls when
the repository has a hosted origin, so Pulls can be present while Commits is not.
A missing tab keeps its number reserved.

The main pane shows a view tab bar when a file kind has more than one view: Document and
Source for Markdown, Tree and Source for structured data, Preview and Source for HTML
with active content, Log, Charts, and Raw JSON for agent logs, Log and Raw JSON for
other JSONL files, and Overview and Treemap for folders.
That bar has no `role=tablist` semantics, unlike the navigation and pull request tab
bars. The pull request page renders its own Conversation, Changes, and Checks tabs.

### Shift and Cmd are inconsistent today

| Binding | Shift today | Cmd today |
| --- | --- | --- |
| `?` (Help) | Allowed, because `?` is typed with Shift on most layouts | Forbidden |
| `T` (Quick Search) | Forbidden: Shift+`T` deliberately does nothing | Forbidden |
| `/` (Quick Search alias) | Forbidden, so `/` never works on a layout that types it with Shift, such as German | Forbidden |
| `1`, `2`, `3` (main tabs) | Forbidden: Shift+`1` does nothing | Required on the preferred binding, ⌘1; the bare digit is an alias |
| Tree, Pulls, and changed-file `J`, `K` | Forbidden by the default policy | Forbidden |
| Git rows `J`, `K` | Rejected by a local guard | Rejected |
| Stack ⇧J, ⇧K | **Required:** the only letters whose meaning Shift changes | Forbidden |
| Tree Shift+↑, Shift+↓ | Required: jump to the first or last row | Forbidden |

A reveal gesture built on Shift cannot coexist with keys that stop working while Shift
is held. The reader would see `T` on the Quick Search hint, press it with Shift still
down, and get nothing; would see `1` on the Files tab and get nothing; and with Shift
held, `J` would mean “toward the stack base” in one place and “next row” in another.

The ⌘ digits shipped in v0.12.0 with a Help note to use the bare digit when the browser
reserves the chord, and the mainstream desktop browsers do: they switch their own tabs
on Cmd+digit or Ctrl+digit.
The bare digit is the binding that actually works there.

### The pieces this plan builds on

- The registry’s `control` binding already connects a command to a rendered element and
  keeps its ARIA state in sync.
  Badge targets generalize it.
- `static/main-tabs.js` already registers one command per main tab and sets
  `aria-keyshortcuts` on each tab button, and the design system already fixes each tab’s
  digit. This plan keeps those commands and changes their bindings, copy, and focus
  target.
- `--row-flash-bg` is the yellow that marks a newly arrived Files or Pulls row.
  It is defined in both themes in `static/styles.css` and is the color the reveal
  reuses.
- The shortcut strip `#nav-shortcut-hints` already renders a registry snapshot for the
  `nav` surface. Reveal adds a second surface rather than a second renderer.
- The
  [contextual keyboard help plan](../done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
  defines the descriptor, scope, formatter, and Help contracts this plan extends.
  Its decision that Shift+`T` is unclaimed is reversed here, for the reason above.

## Design

### Resolved Interaction Model

1. **Shift is never a condition for a letter or digit shortcut.** A letter binding
   matches the letter in either case.
   A digit binding matches the produced digit or, failing that, the physical digit-row
   key, so Shift+`1` on a US layout, which types `!`, still means `1`. A punctuation
   binding matches the character produced, with or without Shift: `?` is its own key,
   Shift+`/` on a US layout is therefore Help, and `/` keeps meaning Quick Search on
   layouts that type it with Shift.
2. **No binding uses Ctrl, Alt, or Meta.** A key event with any of them held never
   matches a shortcut, and the registry rejects a descriptor that requires one.
3. **Holding Shift alone, with the pointer at rest, reveals.** After Shift has been held
   by itself for the hold threshold, with focus outside a text field, the reveal starts.
   Any other key, pointer movement past a small slop, a pointer press, a wheel event, a
   modifier, or losing focus before then cancels it, so `?`, capitals, Shift+Arrow,
   Shift+wheel, and a Shift+click made while the pointer travels never flash badges.
4. **A badge sits on what its key activates.** Badges are keycaps in the `.kbd` family
   with the reveal’s yellow fill, at the target’s inline end, translucent enough that
   the label beneath stays legible.
5. **Pressing a revealed key while still holding Shift runs it and keeps the reveal.**
   Badges then follow the new state, so a reader can press `2`, see the Commits panel’s
   keys, and keep going.
   Releasing Shift ends the reveal.
   The reveal is for keys: a click made with Shift still down is a Shift+click, which
   dismisses the reveal and keeps its browser meaning, such as opening a link in a new
   window.
6. **A key is live only while its target is visible.** `M` means Treemap only while a
   folder’s Treemap tab is on screen; elsewhere it does nothing and the browser keeps
   the event. A main tab that is absent, such as Commits before Git discovery, leaves its
   digit unclaimed.
7. **The strip turns yellow and lists more.** While revealed, the shortcut strip uses
   the reveal fill and lists the common keys, overlaying the bottom of the navigation
   pane’s content instead of resizing it.
8. **Help shows bare keys.** Help, the strip, and every hint write keys exactly as the
   formatter names them: a capital letter, a digit, or the punctuation itself, with no
   Shift and no ⌘. Help ends with one note: “Press `Shift` to see relevant shortcut
   reminders.”
9. **Editable content and modals keep their existing precedence.** Shift in a text field
   types capitals and never reveals; an exclusive modal scope shows only its own keys.

### Key Allocation Rules

Every key belongs to one of three tiers, allocated in this order:

1. **Digits select the navigation pane’s tabs, one fixed digit per tab.** Files is `1`,
   Commits `2`, and Pulls `3`, as the design system’s main tab rule already fixes them.
   A tab that is absent keeps its number reserved, so a digit never moves when Commits
   or Pulls comes and goes.
   A future tab takes the next free digit, up to `9`.
2. **Tab letters select a main-pane tab by its label’s first letter.** A label always
   gets the same letter wherever it appears: Source is `S` for every kind that has a
   Source tab. When the first letter is taken in the same tab bar or by a shell key, the
   tab takes the most distinctive free letter of its label, usually the start of another
   word or syllable: Tree is `R`, Treemap is `M`, for its map, and Changes is `G`, from
   chan-ges, because Conversation holds `C` beside it.
   The key is declared next to the label, not derived at runtime, so renaming a label
   never silently moves a key.
3. **Command letters select a button, menu, or filter.** An established convention wins
   where one exists: `T` and `/` for a file finder and `W` for the branch switcher from
   GitHub, `?` for Help, `J` and `K` for row movement, `N` and `P` for next and previous
   as in Gmail, `U` for “up.”
   Next comes a recorded mnemonic, written in the keymap’s reason column: `Y` for copy,
   as in Vim’s “yank.” Otherwise the command takes the first free letter of its label.

Three constraints hold across the tiers:

- **Uniqueness among co-visible targets.** Two targets that can be visible together
  never share a key. Targets that can never coexist may share one, as Tree and Raw JSON
  share `R`, because no structured file has a Log tab and no log has a Tree tab.
- **Shell keys are reserved where they can be live.** A tab letter or plugin key never
  takes a digit or an always-reserved shell letter: `T`, `J`, `K`, `U`, `W`, `X`, `Y`,
  or `A`. Several of them are live only in some contexts, but they are reserved in all
  of them so a shell key never means one thing here and another there.
  The stack keys `N` and `P` are contextual: they are live only on a pull request page
  in a stack, so they are reserved only for the pull request kind, and the HTML Preview
  tab keeps `P`.
- **No key uses Ctrl, Alt, or Meta,** and no allocation depends on Shift.

The build-time keymap check enforces all three for view and shell keys.
For every file kind it takes the merged view list the server serves for that kind, adds
the always-reserved shell keys and the contextual shell keys whose context includes that
kind, and fails on a duplicate or a reserved key.
Plugin command keys are not known to the build; phase 2 refuses a reserved one at
registration and arbitrates a shared one at dispatch, and the open questions ask whether
built-in plugins should declare theirs so the build can see them too.

### Keymap

| Key | Target | Live while | Tier | Reason |
| --- | --- | --- | --- | --- |
| `?` | Help button in the strip (no badge: it shows its own keycap) | Always | Command | Convention |
| `T` or `/` | Quick Search button in the strip (no badge) | Always | Command | GitHub convention |
| `1` | Files tab | Always | Digit | Fixed |
| `2` | Commits tab | Git discovery has found a repository; reserved otherwise | Digit | Fixed |
| `3` | Pulls tab | The repository has a hosted origin; reserved otherwise | Digit | Fixed |
| `U` | The folder header’s Up button, or for a file the breadcrumb of its folder | The main pane shows a file, or a folder below the root | Command | “Up” convention |
| `Y` | Copy in the main-pane header: a file’s path, or in the commit view the revision | A file or a commit is shown | Command | Mnemonic: “yank”; `C` is a tab letter |
| `W` | Branch or tag switcher | The page is a mirror’s Git pin | Command | GitHub convention |
| `X` | File type filter | The Files tab is shown | Command | Mnemonic: extension, as in `ls -X`; `F` stays free for tabs |
| `A` | Modified within filter | The Files tab is shown on a subject with recency | Command | Mnemonic: age, the design system’s term |
| `J` or `K` | Next or previous row | A tree, Commits, Pulls, or changed-file row has focus | Command | Convention |
| `N` or `P` | Next or previous pull request in the stack (no badge; listed in the strip) | A pull request in a stack is open | Command | Gmail convention |
| `D` | Document tab | A Markdown file is shown | Tab | First letter |
| `S` | Source tab | The kind has more than one view and one is Source | Tab | First letter |
| `P` | Preview tab | An HTML file with active content is shown | Tab | First letter |
| `R` | Tree tab | A structured data file is shown | Tab | `T` is reserved |
| `R` | Raw JSON tab | An agent log or JSONL file is shown | Tab | First letter |
| `L` | Log tab | An agent log or JSONL file is shown | Tab | First letter |
| `C` | Charts tab | An agent log is shown | Tab | First letter |
| `O` | Overview tab | A folder is shown | Tab | First letter |
| `M` | Treemap tab | A folder is shown | Tab | `T` and `R` taken; “map” |
| `C` | Conversation tab (phase 2) | A pull request page is shown | Tab | First letter |
| `G` | Changes tab (phase 2) | A pull request page is shown | Tab | `C` is Conversation; chan-ges |
| `H` | Checks tab (phase 2) | A pull request page is shown | Tab | `C` is Conversation; the next letter |
| `L` | Toggle diff layout (phase 2) | A diff view with a layout control is mounted | Command | Mnemonic: layout |

Letters shared in this table belong to targets that cannot be visible together: Tree and
Raw JSON, Charts and Conversation, the Log tab and the diff layout toggle, and the
Preview tab and the stack’s `P`. The Up target is not attached at the root, where the
folder header’s Up button is disabled.

### Shift Rule Matching

`normalizeBinding()` gains a key class with a fixed Shift policy, replacing per-binding
Shift policies for character keys:

| Key class | Matches | Shift | Ctrl, Alt, Meta |
| --- | --- | --- | --- |
| Letter `a`–`z` | `event.key` in either case | Ignored | Never; the event does not match |
| Digit `1`–`9` | `event.key` equal to the digit; otherwise `event.code` `Digit1`–`Digit9` | Ignored | Never; the event does not match |
| Punctuation `?`, `/` | `event.key` equal to the character | Ignored | Never; the event does not match |
| Named key (arrows, Home, End, Enter, Space, Escape, Delete, F2) | `event.key` | Per binding, as today | Never; the event does not match |

The registry rejects two kinds of descriptor at registration, so the rules cannot erode
one command at a time: one that states a Shift policy on a letter, digit, or punctuation
binding, and one that requires Ctrl, Alt, or Meta on any binding.
The only such bindings on `main` are the ⌘ main tab bindings, which this plan removes
from `tabBindings()` in `static/main-tabs.js`; the formatter keeps its modifier
definitions only to match and forbid them, and the design system’s `Ctrl`+`F` grammar
example gives way to Shift+↑, the one chord left.

Digit matching has a fixed precedence, because one event can name two keys: on German,
Spanish, and Nordic layouts Shift on the physical `7` key types `/`, and on Programmer
Dvorak the digit row types other digits.
The registry first matches every live binding against `event.key`. Only when nothing
matched and `event.key` is not itself a digit does it try a digit binding by
`event.code`. So German Shift+`7` is `/`, Quick Search, and never `7`; US Shift+`1`,
which types `!`, is `1`; and on AZERTY, where the unshifted digit row types `&é"'(`, the
physical match is what makes `1` work at all.
Numpad digits match by `event.key`.

Three consequences follow:

- Tree, Commits, Pulls, and changed-file `J` and `K`, the main tab digits, and Quick
  Search `T` accept Shift.
  The design system’s navigational row contract changes from “unmodified” to “without
  Ctrl, Alt, or Meta” for the letter aliases; the arrow keys are unchanged.
- Stack navigation moves from ⇧J and ⇧K to `N`, next toward the stack’s top, and `P`,
  previous toward its base, in `registerKeys()` in `static/pulls-nav.js`, with the same
  global scope and the same availability while a pull request in a stack is open.
  Shift+`J` on a focused Pulls row now moves the row, as plain `J` does.
- `?` and `/` stay distinct even though they share a physical key on US layouts, because
  punctuation is matched as the character the reader typed and is written that way.
  This is the one place Shift changes the outcome, and only because it changes the
  character. Punctuation still needs no modifier beyond what typing it takes, except on
  layouts that type it with AltGr, which reports Ctrl and Alt and so stays outside the
  rule.

Digits are already in the formatter’s vocabulary, with the digit as markup label, spoken
name, and ARIA token.
The formatter’s spoken and visible output never mentions Shift for a character binding,
and nothing renders `⌘` once the main tab bindings change; `⇧` remains only in the
tree’s Shift+↑ and Shift+↓. A separate single-key entry point, `describeKey()` with
`appendKey()`, renders a key that is not a binding: the `Shift` in Help’s closing note,
which reads as the word Shift rather than the `⇧` glyph a chord uses, and each badge’s
keycap. `Shift` is a key name for that entry point only; the binding validator never
accepts it.

### Reveal State Machine

A new strict module, `static/key-reveal.js`, owns the gesture as a pure state machine
with injected time, focus, and visibility.
It is created by the shell beside the registry and drives presentation only; dispatch
stays in the registry.

| State | Event | Next state and effect |
| --- | --- | --- |
| Idle | Shift `keydown`, not repeated, no Ctrl, Alt, or Meta, target not editable, not composing, no pointer button down | Armed; start the hold timer and note the pointer position |
| Armed | Hold timer fires | Revealed; set `data-key-reveal` on the root and mount badges |
| Armed | Any other `keydown`, `pointermove` past the slop, `pointerdown`, `wheel`, Shift `keyup` | Idle; cancel the timer, nothing painted |
| Revealed | The registry reports a dispatch | Revealed; badges follow their targets |
| Revealed | Any other non-Shift `keydown` | Idle; unmount |
| Revealed | Shift `keyup`, `pointerdown`, `wheel`, Ctrl, Alt, or Meta `keydown` | Idle; unmount |
| Armed or Revealed | Window `blur`, `visibilitychange` to hidden, focus entering an editable target | Idle |
| Any | Any key event whose `shiftKey` is false while the machine thinks Shift is down | Idle; recovers a lost `keyup` |

Repeated Shift `keydown` events while held are ignored, and so are repeated keys the
registry handles while revealed: holding `J` does not re-mount badges on every repeat.

Two constants bound the gesture, each set by measurement and recorded beside it,
following [measure before bounding](../../../large-content-rendering.md):

- `REVEAL_HOLD_MS`, the hold threshold, from the Shift-to-next-key gap of typed `?`,
  capitals, and Shift+Arrow in Chrome and Safari: the smallest value above those
  keyboard chords. The working assumption is about 200 ms; the measurement replaces it.
- `REVEAL_POINTER_SLOP_PX`, the pointer travel that cancels arming, from the jitter of a
  resting hand on a mouse and a trackpad.

A hold timer alone cannot tell a deliberate hold from Shift held while the pointer
travels to a Shift+click, such as the Source gutter’s range selection or a tree row’s
recursive expansion, or from Shift+wheel, the browser’s sideways scroll that a Split
diff relies on.
The slop and wheel exits are what separate them: a Shift+click made after
the pointer has rested past the threshold may briefly reveal, and the click dismisses
it.

The machine listens with passive listeners and never calls `preventDefault()`, so
Shift-click, Shift-selection, Shift+wheel, and every Shift chord keep their browser
behavior. It learns that the registry handled a key from a `dispatch` event the registry
publishes through its existing `subscribe()`, which today carries only `registration`
and `scope` events.
It does not read `defaultPrevented`, which component handlers such as
the Git rows, the gutter, the treemap, and the pull request stack menu also set.
It installs no application-shortcut dispatcher of its own.

### Badge Targets

The registry gains one operation:

```js
const target = shortcuts.attachTarget("filter.type", typeTrigger, {
  placement: "inline-end",
});
target.retarget(nextTypeTrigger); // after a markup rebuild
target.detach(); // idempotent
```

`attachTarget(commandId, element, options)` records the element as the command’s visible
target and returns a handle with `retarget()` and `detach()`, the same shape the phase 2
plugin facade returns.
It replaces the hand-set `aria-keyshortcuts` that `main-tabs.js` writes on the tab
buttons today, so one path owns the attribute.
Components that rebuild their markup through `innerHTML`, as the filter bar does on
every state change, call `retarget()` after each rebuild.
While attached:

- the element carries the formatter’s `aria-keyshortcuts`, permanently, so keyboard and
  screen-reader users learn the key without the reveal;
- the command is live only while the element is connected, visible, not `disabled`, and
  outside an `inert` subtree, checked at dispatch time rather than tracked.
  Visibility is `element.checkVisibility()` where the browser has it; otherwise no
  ancestor has a computed `display` of `none` or `visibility` of `hidden`, which catches
  the inline `display: none` that hides the filter bar on every navigation tab other
  than Files, inactive navigation panels, and inactive preview tab contents.
  The `inert` test applies on both paths, because `checkVisibility()` ignores `inert`
  and `opacity: 0`. During a retained navigation, `stagePreviewNode()` mounts the
  incoming file view, pull request page, or commit view in an `inert`, transparent
  `.preview-file-stage`, and its tabs and controls must not count as live beside the
  visible ones; and
- while revealed, the registry renders one `kbd.kbd.kbd-badge` with `aria-hidden="true"`
  through `appendKey()` and removes it when the reveal ends.
  `attachTarget()` and `retarget()` mount a badge at once when called during a reveal,
  so badges follow targets as components re-render rather than waiting for a moment when
  an asynchronous command has settled.

Badges exist only while revealed, so no target’s `textContent`, layout, or accessible
name changes at rest.
A command may have several targets, such as several mounted diff views.
The first live target in document order runs the command and gets the badge; the others
keep their `aria-keyshortcuts` and wait their turn.
Disposal removes the attribute, any badge, and the record.
The strip’s own Help and Quick Search buttons are never badge targets: they already show
their keycaps.

**Shared letters and registration.** The registry rejects two descriptors in one scope
with the same normalized binding, whether or not their targets are visible, and this
plan keeps that check.
View tab commands are therefore keyed by letter, not by view: `view-tabs.r` is one
command whose targets are the committed tab buttons declaring `R`, and its copy comes
from the label of the bar that registered it.
A view tab bar registers its commands and attaches its targets when it commits to the
preview pane and releases them when it leaves.
A bar still in the inert stage registers nothing, so the outgoing structured file’s `R`
and the incoming log’s `R` never overlap, and a stage that is discarded leaves nothing
behind. Plugin keys, in phase 2, register in a `plugin` scope that sits below `global`,
so the per-scope check never sees a shell and plugin pair and the shell key outranks the
plugin key by scope order.

**No modifier chords.** Registration rejects any binding that requires Ctrl, Alt, or
Meta, so a Cmd or Ctrl shortcut cannot return one command at a time.
The `main-tabs` bindings lose their `meta: "require"` alternative, which today makes
`⌘1`, `⌘2`, and `⌘3` the preferred keys.
Named-key widget bindings may still require Shift, which only the tree’s Shift+↑ and
Shift+↓ do.

**Late registry.** The registry loads in the on-demand `shell-tools` bundle after the
first tree settles. `initDeferredShellTools()` then runs `attachMainTabs()`,
`initKeyboardInfrastructure()`, Quick Search, the Pulls panel, and the Git panel, so
Commits registers its tab after the registry exists.
The source selector arrives in its own on-demand bundle, and the shell disposes the
registry on a real `pagehide` and rebuilds it on `pageshow`. Render sites can therefore
run with no registry.
They report to the shell keymap only when it exists, and `createShellKeymap()` reads the
current state when it is created: the navigation tabs in the tab bar, the committed view
tab bar and its `views[].key`, the main-pane header’s Up and copy controls, the filter
triggers, and the selector handle once its bundle resolves.
Creating the keymap is therefore the same as replaying everything that rendered before
it, on first build and on every rebuild.
`key-reveal.js` and `shell-keymap.js` join the `shell-tools` bundle, beside the
registry, because neither has work before the registry exists; keeping them out of the
eager path follows the
[asset loading tiers](../../../development.md#asset-loading-tiers).
The reserved shell keys reach the browser in `METABROWSER_SETTINGS` from the one Python
table, so the registry and the phase 2 facade refuse the same letters the manifest
loader refuses.

**Placement.** Placement has two forms, and neither covers a glyph or depends on a
container that clips.

- `inline-end` places the badge inside the target, vertically centered over its
  inline-end padding. It is the default for tabs, chips, and text buttons, and because
  the badge stays inside the target’s box, a pill-shaped container such as the diff
  layout chip group clips nothing.
- `beside` places the badge just past the target’s inline end, positioned within the
  nearest ancestor that declares itself a badge anchor and does not clip.
  It is for icon-only buttons and for targets inside `overflow: hidden` containers: the
  file header’s Copy path button, 24 pixels wide inside a clipping path row; the commit
  view’s Copy revision button; and the file breadcrumbs that are Up’s target for a file.
  The file header and the commit view’s heading are the anchors.

Both forms are absolutely positioned, ignore pointer events, and never change the
target’s box. An `inline-end` target becomes its containing block through a
zero-specificity `:where(.kbd-badge-host) { position: relative }`, so a target that
already declares a position keeps it.
A target that is revealed on hover, such as either copy button (`.icon-btn-reveal`,
transparent until hover or focus), is made visible for the duration of the reveal,
extending the design system’s rule that reveal on hover keeps keyboard reach.

**Activation.** Each command runs a named activation path that does what a click does,
plus the focus move a keyboard user needs next.
No command synthesizes a click.

| Command | Activation |
| --- | --- |
| Main tabs | `openMainTab()` (`mainTabs.open`), which owns each tab’s remembered route, then the panel’s new optional `focusRow()` hook: the file tree’s roving row, the current commit row, or the selected pull row, falling back to the tab button while the panel has no rows yet. `1` then `↓` walks the file tree, and a digit for the tab already shown only moves focus. Today the key focuses the tab button |
| View tabs | A new `selectPreviewTab(bar, tabId)`, extracted from the anonymous click listener in `initTabs`, which updates the buttons, shows the content, runs the lazy mount, and calls `setActivePreviewView()`. The click listener and `showPreviewTab()`, which synthesizes a click today, call it too. It also sets `aria-selected`, and the bar it serves gains `role="tablist"` and `role="tab"`, matching the navigation and pull request tab bars. Focus stays where it was |
| Filters | A new named `openFilterMenu(key)`, extracted from the filter bar’s `onMenuToggle` closure, then focus the checked row, or the first row, so the menu’s arrow keys work |
| Branch or tag | The selector’s mounted handle, kept instead of discarded, through the same path as its button: open, then focus its filter field |
| Up | The header navigation path that the Up button and breadcrumbs use |
| Copy | A new `MetabrowserPluginHost.copyFromControl(element)`, a named entry to the shared copy delegate that today only a document click reaches. `Y` copies what the main-pane header identifies: the file header’s path, or the commit view’s revision. The navigation header’s Copy commit on a pin and the per-file copy buttons of a diff get no key |

The `focusRow()` hook joins the `MetabrowserNavPanel` contract beside `onShow` and
`onHide`. `main-tabs.js` supplies it for Files from the tree keyboard controller, and
`git-panel.js` and `pulls-nav.js` supply it when they register Commits and Pulls.

The shell’s commands live in a new strict module, `static/shell-keymap.js`, rather than
in `app.js`. `createShellKeymap({shortcuts, shell})` registers the view tab, header,
filter, and source commands and attaches their targets and the main tab targets, with
every activation function injected by `app.js`. The main tab commands stay in
`main-tabs.js#bindShortcuts` and the pull commands in `pulls-nav.js#registerKeys`, both
already strict and already owners of parity rows.
The parity checker credits only modules a session loads whole, and `app.js` is a legacy
module no session can load that way, so this split is what lets the browserless session
own the keymap.

### Reveal Presentation

The reveal’s visual contract, owned by the `── Keyboard keys ──` block of
`static/styles.css` and documented in the design system:

- **Tokens.** `--key-reveal-bg` is `--row-flash-bg`; `--kbd-badge-bg` is the same color
  with partial alpha; `--kbd-badge-border` is a deeper tone of the same hue;
  `--kbd-badge-color` is the body text color.
  All are `oklch`, defined in both themes, and keep `--row-flash-bg`’s hue, as
  `tests/test_design_vocabulary.py` requires.
- **Contrast.** Text meets 4.5:1 in both themes on everything the reveal paints: a
  badge’s keycap as composited over its target, and the revealed strip’s labels and
  keycaps on `--key-reveal-bg`. The strip’s resting `--muted` text does not meet it on
  the yellow, by an estimate of roughly 4:1 in the light theme and 2.5:1 in the dark, so
  the revealed strip uses `--text`. If the dark theme’s darker `--row-flash-bg` still
  fails with light text, the reveal tokens get their own lightness at the same hue
  rather than a new hue.
  The measured ratios are recorded beside the tokens.
- **Keycap.** A badge is a `.kbd` and inherits its type, caps, and radius; the modifier
  changes only fill, border, and shadow.
  No call site styles a badge.
- **Motion.** The reveal fades in over a short interval; under
  `prefers-reduced-motion: reduce` it appears without a transition.
  Hiding is immediate.
- **Print.** Badges and the revealed strip never print.

### Shortcut Strip in Reveal Mode

The strip keeps rendering the `nav` surface at rest: Help and Quick Search, as today.
While revealed, the same reconciler renders a new `reveal` surface into a second layer,
with `--key-reveal-bg` behind it.
Today the strip is an in-flow, wrapping flex item, so more items in the same host would
grow it and shrink the navigation panel.
The host therefore keeps its resting content and height, and the reveal layer is
absolutely positioned against the host’s bottom edge and grows upward over the panel
content, so the tree, history, or pull list neither reflows nor scrolls under a held
Shift.

The `reveal` surface is a curated list of common keys, not Help:

| Order | Command | Shown when |
| --- | --- | --- |
| 10 | Quick Search | Always |
| 20 | Help | Always |
| 30 | Files | Always |
| 40 | Commits | The Commits tab exists |
| 50 | Pulls | The Pulls tab exists |
| 60 | Up | Its target is visible |
| 70 | Copy | Its target is visible |
| 80 | Branch | Its target is visible |
| 90 | Stack (`N` or `P`) | A pull request in a stack is open |

The main tab commands join the `reveal` surface, which they lack today: on main they are
on the `help` surface only.
View tabs and filters are left to their badges, which already say where their keys go.
The stack keys have no single target to badge, because a page can carry one stack menu
per stack it belongs to, so the strip is where they are shown.
Row movement is left out for the reason the earlier plan left tree keys out of the
strip: the arrows are what a reader tries first, and the Git rows’ `J` and `K` have no
descriptor to present.
The list is short enough to need no layout measurement: a fixed maximum item count,
chosen by measuring the minimum navigation-pane width in a browser and recorded beside
the surface definition, caps it, and items later in the order drop first and remain in
Help.

### Help Changes

Help keeps the groups main already has, in their order: Anywhere, Main tabs, Navigation,
Pull requests, Pull request stack, Quick Search, and Help.
This plan changes them as follows:

- **Main tabs** shows `1`, `2`, and `3` alone, with no `⌘`. Its context sentence, today
  “Use the number alone if your browser reserves Command and numbers,” becomes
  “Available outside text fields.”
  Each tab’s copy stays “Open Files,” “Open Commits,” and “Open Pulls.”
- **Pull request stack** shows `N` and `P` instead of `⇧`+`J` and `⇧`+`K`.
- A new **View tabs** group, ordered after Main tabs, holds the current file’s view tab
  commands and, in phase 2, the pull request page’s tabs.
  Its context sentence: “Available while the file’s tabs are shown.”
- A new **Controls** group holds Up, Copy, and Branch, and in phase 2 in-view plugin
  commands such as the diff layout toggle.
  Its context sentence: “Available while the control is shown.”
  Anywhere keeps its meaning, “Available outside text fields,” for Help and Quick Search
  only.
- A new **Filters** group holds File type and Modified within.
  Its context sentence: “Available while the Files tab is shown.”
- Every key is written as the formatter names it: a capital letter, a digit, or the
  punctuation itself. No character binding shows `⇧` or `⌘`; the only remaining modifier
  glyph in Help is the tree’s `⇧`+`↑` and `⇧`+`↓`.
- After the last group, Help renders the note “Press `Shift` to see relevant shortcut
  reminders.” with `Shift` rendered by `appendKey()` as a `.kbd`, per the design system’s
  rule that a key in prose is always a keycap.
  The single-key entry point renders a standalone modifier by its name, so the keycap
  reads “Shift,” while a chord keeps the `⇧` glyph.
  The note is guidance for after Help closes; inside Help’s exclusive scope, holding
  Shift shows only Help’s own keys.

Command copy follows the
[Shortcut and Help copy](../../../design-system.md#shortcut-and-help-copy) rules:

| Command ID | Group | Key | Action | Help description | Hint |
| --- | --- | --- | --- | --- | --- |
| `main-tabs.files` | `main-tabs` | `1` | Open Files | Switch to the Files tab when available. | Files |
| `main-tabs.git` | `main-tabs` | `2` | Open Commits | Switch to the Commits tab when available. | Commits |
| `main-tabs.pulls` | `main-tabs` | `3` | Open Pulls | Switch to the Pulls tab when available. | Pulls |
| `pulls.stack.top` | `pull-stack` | `N` | Next in stack | Open the next pull request toward the top of the stack. | Next |
| `pulls.stack.base` | `pull-stack` | `P` | Previous in stack | Open the previous pull request toward the stack base. | Previous |
| `view-tabs.<letter>` | `view-tabs` | Declared | The bar’s label | Show the file’s *label* view in the main pane. | The bar’s label |
| `header.parent` | `controls` | `U` | Parent folder | Open the folder that contains the current file or folder. | Up |
| `header.copy` | `controls` | `Y` | Copy | Copy the path of the current file, or the revision of the current commit. | Copy |
| `source.switch-ref` | `controls` | `W` | Branch or tag | Choose another branch or tag of the served repository. | Branch |
| `filter.type` | `filters` | `X` | File type | Open the file type filter. | File type |
| `filter.recency` | `filters` | `A` | Modified within | Open the modified-within filter. | Modified |

The main tab commands keep their ids, copy, and fixed digits; only their bindings, their
group’s context sentence, and their surfaces change.
A missing tab keeps its number reserved, as the design system already says, so Pulls is
`3` while Commits is still being discovered.
The stack commands keep their ids and `available` test; their stack-menu copy for the
action and hint is new because the old keys were described by direction alone.
View tab command IDs are per letter, for the registration reason under Badge Targets;
the registry’s presentation is frozen at registration, so a view tab command takes its
copy from the bar that registered it, and a bar that commits re-registers its letters.

### Where View Keys Are Declared

View keys are data, so they belong to the route that already carries views.
A view’s served entry comes from `_views_for_kind()`, which starts from `VIEW_REGISTRY`
in `file_kinds.py` and replaces any entry whose id a plugin manifest `[[view]]` also
declares. Every kind with a non-empty `VIEW_REGISTRY` entry (agent log, JSONL, Markdown,
and text) is fully redeclared by its built-in manifest, so a key written on a
`VIEW_REGISTRY` entry would never reach the browser.
The key therefore goes only on built-in manifest `[[view]]` entries, as an optional
single-letter `key`, on every view of a multi-view kind: Markdown, agent log, JSONL,
HTML, folder, and structured data.
`VIEW_REGISTRY` gets no keys.
The file envelope’s `views[]` entries carry the key.

| Kind | Views and keys |
| --- | --- |
| Markdown | Document `D`, Source `S` |
| Structured data | Tree `R`, Source `S` |
| HTML with active content | Preview `P`, Source `S` |
| Agent log | Log `L`, Charts `C`, Raw JSON `R` |
| JSONL | Log `L`, Raw JSON `R` |
| Folder | Overview `O`, Treemap `M` |

Single-view kinds (text, image, binary, diff, pull request, and the pull request list)
draw no tab bar and declare no key.
An HTML file without active content drops Preview in `_html_kind_views()`, leaves one
view, and so draws no tab bar either.

Goldens pin the keys in two places, because no single golden prints every kind’s views:
`metab --show` prints each view’s key on its views line, so `cli-show.tryscript.md` pins
structured data, agent logs, JSONL, and HTML; and the `/api/file` envelopes in
`cli-api.tryscript.md` and `cli-api-hidden-folder.tryscript.md` pin Markdown and
folders. A changed key is a golden diff either way.

Validation has two levels.
The manifest loader checks one manifest at a time: a key is one letter and not an
always-reserved shell key.
Uniqueness among a kind’s views, and against contextual shell keys, spans manifests and
overrides, so it is checked on the merged `_views_for_kind()` output, by the keymap test
at build time and by `metab --doctor` at run time.
At run time a duplicate keeps the first view’s key, drops the later view’s key, and
reports it through `--doctor`; it never refuses the plugin.
A view without a key simply has no key and no badge.
The reserved shell keys live in one Python table, with each contextual key’s kinds, and
the browserless session’s golden prints the shell keys the registry actually registers,
so a Python test can fail when the two drift.

The optional manifest field is an additive internal-contract change: it ships with the
server and every built-in plugin in one commit and is noted in `CHANGELOG.md`, and it
does not change `PLUGIN_SDK_VERSION`.

### Accessibility

- Every target carries `aria-keyshortcuts` at rest; the reveal is a visual aid on top of
  it and is never announced.
  Main tab buttons lose the `Meta+1` token they announce today and keep `1`.
- Badges are `aria-hidden` and the revealed strip’s content changes are not a live
  region, matching the existing hint contract.
- Character keys still act only outside text fields, so typing, dictation, and IME
  composition are unaffected.
- The main-pane view tab bar gains the tablist semantics the navigation and pull request
  tab bars already have.
- A reader who cannot hold a key still has Help, `aria-keyshortcuts`, and every
  control’s Tab and pointer path; a latched reveal is an open question below.

### Performance

Revealing must feel instant, in line with the project’s “effortlessly fast” principle.
The reveal does work proportional to the number of attached targets, which is a few
dozen at most: one root attribute, one visibility read per target to decide which get
badges, one position read per `beside` badge, one badge per live target, and one strip
reconciliation. It fetches nothing, measures nothing for the strip, and does no work on
repeated keys. At dispatch, visibility is read only for the targets of the one command
that matched. Per-render view tab registration adds one registry publication per
committed tab bar, and Help, which re-renders on every registration, renders only while
open. The session records the mount count, and the browser pass records the reveal’s
interaction-to-paint time on the largest fixture.

### File and Function Map

The map names functions rather than line numbers so it survives edits.
Paths are under `src/metabrowser/` unless they begin with `tests/` or `docs/`.

**Phase 1 production code**

| File | Functions | Change |
| --- | --- | --- |
| `static/keyboard-shortcuts.js` | `KEY_DEFINITIONS`, `keyDefinition` | Digits are already accepted; add the single-key `describeKey()` and `appendKey()` entry points, which alone accept a standalone `Shift` and render it by name |
|  | `normalizeBinding`, `validateCommand`, `bindingSignature` | Key classes; reject a Shift policy on a character binding; reject a binding that requires Ctrl, Alt, or Meta; signatures ignore Shift for characters, so a duplicate cannot hide behind a policy |
|  | `eventMatchesBinding` | Shift ignored for characters; digit match by `event.key` first and by `event.code` only after nothing matched by key |
|  | `GROUP_DEFINITIONS` | `view-tabs`, `controls`, and `filters` groups; the `main-tabs` context sentence without Command |
|  | `create`: `register`, `handleKeydown`, `snapshot`, `subscribe`, returned API | `attachTarget()` with dispatch-time visibility and first-live-target choice; badge mount and unmount, immediate during a reveal; a `dispatch` event through `subscribe()`; the `plugin` scope below `global`; `reveal` surface |
| `static/key-reveal.js` (new, strict) | `createKeyReveal` | The state machine, the root attribute, and calls into the registry’s badge mount |
| `static/shell-keymap.js` (new, strict) | `createShellKeymap` | View tab, header, filter, and source commands; all shell targets, including the main tabs; activation injected |
| `static/main-tabs.js` | `MAIN_TABS`, `tabBindings` | Drop the `meta: "require"` binding; each tab keeps its bare digit |
|  | `bindShortcuts` | Join the `reveal` surface; the handler runs `openMainTab()` and then the panel’s `focusRow()`, falling back to the tab button; targets come from `attachTarget()` instead of hand-set `aria-keyshortcuts` |
|  | `registerNavPanel`, `ensureNavPanelElements`, `removeNavPanel`, `activateNavPanel` | Attach and detach main tab targets as Commits and Pulls arrive and leave; keep the fixed digits and reserved gaps; supply Files’ `focusRow()` |
| `static/pulls-nav.js` | `registerKeys` | `pulls.stack.top` becomes `N` and `pulls.stack.base` becomes `P`, without Shift; both join the `reveal` surface; the `pull-rows` and `pull-files` `J` and `K` follow the Shift rule |
|  | `createPullsNav` | Supply the Pulls panel’s `focusRow()` |
| `static/keyboard-help.js` | `buildHelpContent`, `renderHelpGroups`, `reconcileHintStrip`, `create` | Closing Shift note; strip renders `reveal` while revealed; `?` bindings lose their Shift policy |
| `static/search-palette.js` | `registerCommands` | `quick-file.open` follows the Shift rule and joins the `reveal` surface |
| `static/tree-keyboard-navigation.js` | `registerCommands` | `J` and `K` follow the Shift rule; Shift+↑ and Shift+↓ keep their required Shift |
| `static/git-panel.js` | `handleCommitRowKeydown`, the Commits `registerNavPanel` call, the revision copy button | Split the modifier guard: `J` and `K` ignore Shift, the arrows keep it; supply the Commits panel’s `focusRow()`; mark the commit heading as the `beside` badge anchor for `Y` |
| `static/app.js` | `initKeyboardInfrastructure`, `disposeKeyboardInfrastructure` | Create and dispose the reveal module and shell keymap |
|  | `initTabs`, `showPreviewTab`, new `selectPreviewTab` | Extract the tab switch from the anonymous click listener so the key, the click, and `showPreviewTab()` share it; set tablist semantics |
|  | `renderFile` (preview tab bar and stage commit) | Render the bar with `role="tablist"`; register view tab letters and attach targets when the bar commits, never from the inert stage; release them when it leaves |
|  | `renderNavFilterBar`, `initFilterBar`, new `openFilterMenu` | Retarget `X` and `A` after each rebuild; extract the menu-open path from the `onMenuToggle` closure and move focus into the open menu |
|  | `renderFolderHeader`, `renderFile` (header copy and breadcrumbs) | Attach Up, except at the root, and Copy; mark the file header as the `beside` badge anchor |
|  | `startSourceRefSelector` | Keep the mounted handle for `W`, and hand it to the shell keymap when the bundle resolves |
| `static/plugin-sdk.js` | `MetabrowserPluginHost` | `copyFromControl(element)`, a named entry to the copy delegate |
| `static/styles.css` | `── Keyboard keys ──` blocks, `.nav-shortcut-hints` | Badge and reveal tokens in both themes, `.kbd-badge` after the base `.kbd` rule, host rule, reveal-on-hover override, strip overlay, reduced motion, print |
| `static/types.d.ts` | Registry types, `MetabrowserNavPanel`, window globals | `attachTarget`, `focusRow`, the reveal runtime, the shell keymap |
| `file_kinds.py` | Reserved shell key table | Always-reserved keys, and contextual keys with the kinds they apply to; `VIEW_REGISTRY` is unchanged |
| `plugin_loader/manifest.py` | `ViewSpec` | Optional `key`: one letter, not an always-reserved shell key |
| `server.py` | `_views_for_kind`, view serialization, `shell-tools` bundle, page settings, `--show` and `--doctor` output | `views[].key`, with first-wins duplicate handling on the merged list; new modules in the bundle; reserved keys in `METABROWSER_SETTINGS`; keys on the `--show` views line; the duplicate report |
| Built-in `manifest.toml` | `markdown`, `agent_log`, `unknown_jsonl`, `html`, `folder`, `structured` | `key` on each view |
| `devtools/check_distribution.py` | `KEYBOARD_STATIC_ASSETS` | List the two new modules |

**Existing tests whose assertions change**

| Test | Today | After |
| --- | --- | --- |
| `tests/dom/keyboard-shortcuts-behavior.js` | Shift+`J` does not match `{key: "j"}`; fixtures declare Shift policies on `?` and `/`; a Shift+`J` fixture formats as `⇧`+`J`, “Shift plus J”; a `Ctrl`+`F` chord fixture | Shift+`J` matches; character fixtures drop their Shift policies; the Shift+`J` and `Ctrl`+`F` fixtures are replaced by tests that a character Shift policy and a required Ctrl, Alt, or Meta are rejected; group order includes `view-tabs`, `controls`, and `filters` |
| `tests/dom/preview-pane-state-session.js` | `⌘2` is unhandled without Commits and `⌘3` handled; `⌘`+Shift+`2` is unhandled; plain `1` is “the browser fallback”; Help speaks “Command plus 1 or 1” | Only bare digits exist; Shift+`2` behaves as `2`; Help speaks “1” |
| `tests/golden/cli-ui-file-lifecycle.tryscript.md` | Main tab `ariaKeys` are `Meta+1 1`, `Meta+2 2`, `Meta+3 3` | `1`, `2`, `3` |
| `tests/dom/pulls-nav-session.js`, `tests/golden/cli-ui-pulls-nav.tryscript.md` | Shift+`J` and Shift+`K` move through the stack, even with a row focused; Help speaks “Shift plus J” | `N` and `P` move through the stack; Shift+`J` on a focused row moves the row; Help shows `N` and `P` |
| `tests/dom/search-palette-behavior.js` | Shift+`T` and a shifted `/` leave Quick Search closed | Both open it; `?` still does not |
| `tests/dom/tree-keyboard-navigation-behavior.js` | Shift with `J` or `K` does not move | It moves; Alt, Ctrl, and Meta still do not |
| `tests/dom/git-panel-behavior.js` | Shift with `J` or `K` is ignored | It moves; Shift with an arrow is still ignored |
| `tests/dom/keyboard-help-behavior.js` | The strip holds exactly Help and Quick Search; Help headings are exactly Anywhere, Navigation, Help | Unchanged at rest; new cases for the reveal surface, the new groups, and the closing note |
| `tests/test_chrome_typography.py` | Pins Quick Search’s bindings and surfaces string; the first `.kbd` rule uses the key tokens; only the registry creates `<kbd>` | Surfaces string includes `reveal`; `.kbd-badge` follows the base rule; badges are created through `appendKey()` |
| `tests/test_quick_file_integration.py`, `tests/test_keyboard_help_integration.py`, `tests/test_tree_keyboard_integration.py` | `shell-tools` asset order; `test_registry_is_the_only_application_shortcut_dispatcher` names the modules that may not add a document `keydown` listener | New modules in the order; the dispatcher test names `key-reveal.js` and `shell-keymap.js`, and `main-tabs.js` and `pulls-nav.js`, which it leaves out today |
| `tests/golden/cli-show.tryscript.md`, `cli-api.tryscript.md`, `cli-api-hidden-folder.tryscript.md` | Views without keys | Views with keys |

No existing test asserts that a key outside the vocabulary throws; digit formatting is
already pinned by the main tab session.
Two design-vocabulary checks constrain the new CSS: a class name containing `tab` may
not set color or spacing, so no badge class is named for tabs; and a themed `oklch`
token must keep the same hue string in both themes, which the badge tokens satisfy by
reusing `--row-flash-bg`’s hue.
The row-contract check that requires `"j"` and `"k"` in the tree, Git, and Pulls sources
still holds.

**Docs updated in the same change**

- `docs/design-system.md`:
  - Keyboard Keys;
  - Canonical Key Names: remove the Command modifier row, add the standalone `Shift` key
    name for `appendKey()`, and drop the stale sentence that begins “When modifier
    bindings are introduced”;
  - Main Tab Shortcuts: bare digits only, no `⌘`, the reserved gaps kept;
  - Binding Grammar: the Shift rule, with Shift+↑ replacing the `Ctrl`+`F` example;
  - the pull request stack text in The Pull Request Page, and the Pulls Tab’s keys: `N`
    and `P` instead of `⇧J` and `⇧K`;
  - Keyboard Commands and Help: badge targets and the reveal;
  - Navigational Row Collections: the letter aliases ignore Shift;
  - Descriptor Contract: no Shift policy on characters and no required Ctrl, Alt, or
    Meta;
  - Shortcut and Help Copy: the closing note;
  - the overlay lifecycle and accessibility checklist sentences about the single
    dispatcher
- `docs/project/architecture/arch-views-models-routes.md`: the new functional rows; the
  existing `navigation.main-tab-destinations` and `github.pulls-tab-host` rows, whose
  goldens change; and the kinds table, whose pull request row still says “Files changed”
- `docs/development.md`: the `shell-tools` tier row
- `docs/plugins.md`: `[[view]] key`
- `README.md`: the keyboard paragraph
- `docs/reviewing-pull-requests.md` and `docs/e2e-testing.md`: the stack keys
- `docs/e2e-testing.md` and `docs/qa-v012-repository-library.md`: the manual reveal
  check, in section 3.4 and its Safari and Firefox repeat, and `W` in section 5.10
- `CHANGELOG.md`, under Unreleased: `⌘1` through `⌘3` are gone and the bare digits
  remain; `N` and `P` replace `⇧J` and `⇧K`; Shift no longer changes any letter or digit
  shortcut; and the reveal and new keys.
  Both removed bindings shipped in 0.12.0, and no alias for them is kept

### Phase 2: Plugin Shortcut Surface

Phase 2 adds one namespace to the public SDK, `window.metabrowser.shortcuts`, so a
plugin view can give one of its own controls a letter key and a badge target.
It does not expose the registry: plugins name a letter, an element, copy, and an
activation function, and the SDK supplies everything else.

**Where it lives.** Plugin code can run before the registry exists.
`keyboard-shortcuts.js` loads in the on-demand `shell-tools` bundle after the first tree
settles (`server.py`, `"shell-tools"`), and `app.js` creates the registry in
`initKeyboardInfrastructure()`, disposes it on a real `pagehide`, and rebuilds it on
`pageshow`. A pull request page opened by URL can render before any of that.
The namespace is therefore split across two tiers.
The eager `plugin-sdk.js` holds only `mb.shortcuts.attach()` and an attachment queue,
next to `fileCatalog`; `fileCatalog.subscribe` drops a subscription made before
attachment, and the queue does not.
Validation, reserved-letter refusal, arbitration, and replay live in a new strict
module, `static/plugin-shortcuts.js`, in the `shell-tools` bundle, which
`initKeyboardInfrastructure()` connects with `attachShortcutRegistry(registry)` and
`disposeKeyboardInfrastructure()` disconnects.
It replays the queue onto each registry it is given, so keys survive a late registry and
a bfcache rebuild. No request is added to startup, and the eager addition is small by
construction; its transferred bytes are measured against the gated startup script budget
and recorded beside the queue, as
[justifying a tier](../../../development.md#justifying-a-tier) requires, since earlier
work moved code out of `plugin-sdk.js` for exactly this cost.
`plugin-sdk.js` is outside the strict TypeScript gate, which is a second reason to keep
its share minimal.

**API.** One function, returning one handle:

```js
const handle = mb.shortcuts.attach(element, {
  id: "diff.layout",      // dotted; registered under a prefix no shell command uses
  key: "l",               // one ASCII letter, case ignored
  group: "controls",      // "view-tabs" or "controls"
  order: 10,
  copy: { action, description, hint },
  activate: () => {},     // the control's own activation path, never a synthesized click
  signal,                 // optional AbortSignal; abort detaches
});
handle.retarget(nextElement); // move aria-keyshortcuts and the badge
handle.detach();              // idempotent
```

The descriptor has no bindings, modifiers, scope, surfaces, `allowInEditable`, or
`repeat`, because the facade fixes them.
A plugin key is a single letter with the phase 1 Shift policy and no Ctrl, Alt, or Meta,
which the registry would reject anyway.
It registers in the `plugin` scope below `global`, so a shell key outranks it and the
exclusive Help and Quick Search scopes silence it.
It appears on the `help` surface while live, is not listed in the reveal strip, and
never fires in an editable target or on repeat.
Plugins cannot define groups, which the non-goals already exclude; `view-tabs` and
`controls` both come from phase 1. Each attachment is a phase 1 badge target.
The element carries `aria-keyshortcuts` while attached, and the key is live only while
the element is connected, visible, and outside an `inert` subtree.
That last condition matters for every plugin surface, not only file views: the shell
stages the pull request page and the Git commit view, like a file, in an inert,
transparent node through `stagePreviewNode()` before it commits them to the main pane.

**Lifetime.** An attachment lasts until `detach()` or until its signal aborts, and a
plugin detaches from its render handle’s `dispose()`. Disconnection does not end an
attachment. The pull request page’s `paintHeader` removes the tab column while the page
has no record and re-inserts it after the header, and the keys must come back with it.
As a safety net, the view-composition disposer (`view-composition.js` `mount`) also
releases attachments inside the container it disposes.
That net does not reach the diff view, which three hosts mount by calling its renderer
directly: file views through view composition, the Git commit view (`git-panel.js`,
`getRegisteredView("diff", "diff")`), and the pull request page’s Changes tab
(`pull-page.js` `mountDiff`). Each host disposes the handle it gets back, so the diff
view’s own `dispose()` is the reliable path in all three.

**Pull request tabs.** The page’s tabs are Conversation, Changes, and Checks (`TABS` in
`pull-page.js`), rendered once per page as `a.tab-btn[role=tab]` links in a
`role=tablist` bar and kept across paints.
All three labels start with `C`, so the letters follow the allocation rule’s fallback to
a distinctive letter of the label:

| Tab | Route tab | Key | Reason |
| --- | --- | --- | --- |
| Conversation | `""` | `C` | First letter; the default tab keeps it |
| Changes | `"files"` | `G` | `C` taken; chan-*g*es |
| Checks | `"checks"` | `H` | `C` taken; the next letter of the label |

`C` is also the Charts tab’s letter, which is never on screen with a pull request page.
The keys run the page handle’s existing `setTab(next)`, which already owns the route: a
call from beside the page goes through `open()`, so the address moves and Back behaves
as it does after a click.
The wiring is a small exported, literally named function, so the parity checker can
credit it and the existing mount session can run it against a mounted page:

```js
export function attachTabKeys(shortcuts, tabLinks, setTab, signal) {
  for (const [index, { id, link }] of tabLinks.entries()) {
    const tab = TAB_KEYS[id]; // "": C, Conversation; "files": G, Changes; "checks": H, Checks
    shortcuts?.attach(link, {
      id: `github.pull.tab.${id || "conversation"}`,
      key: tab.key, group: "view-tabs", order: 10 + index,
      copy: { action: tab.label, description: tab.description, hint: tab.label },
      activate: () => setTab(id),
      signal,
    });
  }
}
// In mountPullPage, once `tabLinks` and `listening` exist; cancelPending() aborts it.
attachTabKeys(mb.shortcuts, tabLinks, (tab) => page.setTab(tab), listening.signal);
```

The stack keys `N` and `P` stay with the shell, in `static/pulls-nav.js`, where the
stack commands already live; phase 2 adds nothing for them.

**Diff layout toggle.** `L` calls a new exported `toggleLayout(view)`, which runs
`setLayout(view, view.layout === "split" ? "unified" : "split")`. Because it goes
through `setLayout`, `L` behaves exactly like a click: where Split does not fit, `L`
chooses Split and its sideways scroll, as clicking Split does.
The badge sits on the option `L` would select, the chip with `aria-checked="false"`.
`renderLayoutControl()` rebuilds the chips through `innerHTML`, so it calls
`view.layoutKey?.retarget(...)` after each draw.
`renderDiffToolbar()` attaches once, after its first draw, and the view’s `dispose()`
detaches. The diff reads the facade as `view.api?.shortcuts`, as it already reads
`view.api?.filterControls`. Each host’s render reaches `mountDiffView` with the same
`window.metabrowser` that `diff/index.js` binds at load, so diff files, the Git commit
view, and the pull request page’s Changes tab all get `L` with no change to
`git-panel.js`.

**Collisions.** Malformed input is a programming error.
It throws an error prefixed `shortcuts.attach:`, as `registerView` and
`fileCatalog.subscribe` do with their own prefixes.
That covers an element that is not an `HTMLElement`, a key that is not one letter, an
unknown group, a missing `activate`, and a reused `id` whose key, group, or copy
differs. Key conflicts do not throw, because the shell may reserve a new letter later,
and that must not turn a working view into a render failure:

- A shell-owned letter is never bound to a plugin: the always-reserved `T`, `J`, `K`,
  `U`, `W`, `X`, `Y`, and `A`, and the contextual `N` and `P`. The facade cannot know
  which kinds a plugin view will appear in, so it refuses the contextual letters in
  every context, as it refuses digits.
  The attachment gets no `aria-keyshortcuts`, no badge, and no Help entry, and the
  facade logs one `console.warn` for each command ID, following `prefs.set`’s
  warn-and-ignore convention (`plugin-sdk.js` `prefsSet`).
- A letter that another live target holds is settled at dispatch and reveal time, when
  co-visibility is known.
  A shell target beats a plugin target, as the Log tab’s `L` would beat the diff toggle.
  Between plugins, the earlier attachment wins.
  Only the winner runs and gets a badge, and the loser’s ID gets one warning.
  The facade registers one `plugin`-scope command per letter and arbitrates among its
  own targets, so the registry’s same-scope duplicate-binding error is unreachable from
  plugin input, and the shell’s `global` scope settles a shell and plugin pair.
- Two mounts of one ID, such as two diff views, are one command with two targets.
  Each target has its own `activate`, so only the first visible target runs and gets a
  badge.

**SDK version.** `PLUGIN_SDK_VERSION` stays `0.7`. `docs/plugins.md` bumps it “only when
the contract actually breaks”.
The architecture map’s planned-surfaces section treats a capability as additive when
existing 0.7 manifests and calls keep their signatures and behavior, though docs and a
changelog entry are still required.
`CHANGELOG.md` has the precedent “`PLUGIN_SDK_VERSION` remains `0.5`” for added SDK
helpers. No existing call changes, and no built-in plugin handles a letter key: the key
handlers under `builtin_plugins/` are the agent log’s Enter and Space, the treemap’s
arrows, Enter, Space, and Backspace, the pull request stack menu’s Enter, Space, Escape,
Tab, arrows, Home, and End, with a document-level Escape, and the diff view’s and pull
request page’s passive scroll-pin release.
The pull request page’s tab links are anchors, so a click made with Shift still held
opens a new window there, as it does anywhere else.
External plugins feature-detect with `mb.shortcuts?.attach`, just as `types.d.ts` types
`filterControls` as optional.

**Docs.** In `docs/plugins.md`, add a Keyboard Shortcuts subsection under Browser SDK
after Data and Navigation, put `shortcuts` in the SDK list under Rendering and
Formatting, and add a Testing Checklist item: every attachment detaches in `dispose`,
and the view’s session prints no shortcut warning.
Also update the `plugin-sdk.js` header comment, `MetabrowserSdk` in `types.d.ts`, and
`CHANGELOG.md` under Unreleased (Plugin SDK, version unchanged), and add a row to the
planned plugin registration surfaces table.

**Tests and goldens.** Each is an interaction row:

| Aspect | Owner | Data inputs | Session | Golden |
| --- | --- | --- | --- | --- |
| `plugins.shortcut-surface` | `static/plugin-shortcuts.js#attachShortcut`, `static/plugin-shortcuts.js#attachShortcutRegistry` | `local-only` | new `tests/dom/plugin-shortcuts-session.js` | new `cli-ui-plugin-shortcuts.tryscript.md` |
| `github.pull-page-tab-keys` | `builtin_plugins/github/pull-page.js#attachTabKeys` | `/api/plugin/github/pull` | `tests/dom/github-pull-page-mount-behavior.js` | `cli-ui-github-pull-page.tryscript.md` |
| `diff.layout-key` | `builtin_plugins/diff/diff-view.js#toggleLayout`, `builtin_plugins/diff/diff-view.js#setLayout` | `local-only` | `tests/dom/diff-layout-fit-session.js` | `cli-ui-diff-layout-fit.tryscript.md` |

The surface session loads `plugin-sdk.js` and `plugin-shortcuts.js` whole, as other DOM
sessions do. Every owner is a literally named function declaration: V8 names an
object-literal method after its property, so a method `attach` would never credit
`attachShortcut`. It covers attachment before a registry exists and the replay,
dispatch, reveal, and the Help snapshot.
It also covers a refused `T`, a refused `N`, two plugins on one letter, a target removed
and re-inserted, a target under `inert`, abort and idempotent detach, and registry
teardown and rebuild.
The pull request tab keys extend the mount session that already pins the Checks tab
(`github.pull-checks-tab`), because the tab links are built inside `mountPullPage`: it
prints `C`, `G`, and `H` moving the route through `setTab`, the same with Shift, and the
keys returning after `paintHeader` re-inserts the tab column.
The layout session, which already pins `diff.layout-fit` through `setLayout`, adds a
`shortcuts` stand-in to its fake `api` and prints `L` on a wide diff, `L` after Split
falls back, the retarget after each draw, and the preference it writes.
The stack keys need no phase 2 row: `github.pulls-tab-host` already owns
`pulls-nav.js#registerKeys`, and `github.native-stack-ui` already owns the stack
membership those keys walk.
Badge geometry stays under phase 1’s paint-exempt row.

### API Changes

- **Registry** (internal): letter, digit, and punctuation bindings take a fixed Shift
  policy; a binding that requires Ctrl, Alt, or Meta is rejected at registration; digit
  precedence; `attachTarget()`; `describeKey()` and `appendKey()`; a `dispatch` event; a
  `plugin` scope below `global`; `reveal` surface; `view-tabs`, `controls`, and
  `filters` groups; the `main-tabs` group’s context sentence becomes “Available outside
  text fields.”
- **Main tabs** (internal, `static/main-tabs.js`): `tabBindings()` returns only the bare
  digit; the key runs `openMainTab()` and then focuses the panel’s roving row.
- **Pull keys** (internal, `static/pulls-nav.js` `registerKeys`): `pulls.stack.base` on
  `P` and `pulls.stack.top` on `N`; row and changed-file `J` and `K` ignore Shift.
- **`/api/file` envelope**: `views[].key`, optional.
- **Plugin manifest**: optional `[[view]] key`.
- **`window.metabrowser`** (phase 2): the `shortcuts` namespace described above.
  `PLUGIN_SDK_VERSION` stays unchanged.
- **`MetabrowserPluginHost`** (internal): `copyFromControl()` in phase 1 and
  `attachShortcutRegistry()` in phase 2.
- **`METABROWSER_SETTINGS`**: the reserved shell keys, with the contexts of `N` and `P`.
- **`metab --show`**: each view’s key on the views line.
- **Behavior changes to released v0.12.0 behavior**, recorded under `## Unreleased` in
  `CHANGELOG.md` with no alias kept for the old keys:
  - `⌘1`, `⌘2`, and `⌘3` no longer open Files, Commits, and Pulls; `1`, `2`, and `3` do,
    with or without Shift, and the browser keeps its Command chords;
  - Shift+`J` and Shift+`K` no longer walk a pull request stack; `N` moves toward the
    top and `P` toward the base, with or without Shift;
  - Shift+`T`, Shift+`J`, and Shift+`K` now act as `T`, `J`, and `K`, and `/` now works
    on layouts that type it with Shift.

## Implementation Plan

### Phase 1: Shift Rule, Keymap, and Reveal in the Core Shell

- [ ] Registry: key classes with the fixed Shift policy, rejection of a required Ctrl,
  Alt, or Meta, digit precedence, `describeKey()` and `appendKey()`, rejection of
  character-binding Shift policies, `view-tabs`, `controls`, and `filters` groups and
  the new `main-tabs` context sentence, the `dispatch` event, the `plugin` scope,
  `reveal` surface, and `attachTarget()` with dispatch-time visibility and immediate
  badges during a reveal
- [ ] Remove Cmd: drop the `meta: "require"` binding from `tabBindings()` in
  `static/main-tabs.js`, so Files, Commits, and Pulls answer to `1`, `2`, and `3` alone,
  and remove `⌘` from Help, the design system’s Main Tab Shortcuts section and Canonical
  Key Names, and new changelog wording
- [ ] Main tabs: the key runs `openMainTab()`, then focuses the panel’s roving row,
  falling back to the tab button; a missing tab keeps its number reserved
- [ ] Stack keys: move `pulls.stack.base` and `pulls.stack.top` from Shift+`J` and
  Shift+`K` to `P` and `N` in `static/pulls-nav.js` `registerKeys`
- [ ] Migrate Quick Search, tree `J` and `K`, Git row `J` and `K`, and the Pulls
  `pull-rows` and `pull-files` `J` and `K` to the Shift rule
- [ ] Declared view keys: `key` on every built-in manifest view of a multi-view kind,
  envelope `views[].key`, keys on the `--show` views line, loader validation,
  merged-list uniqueness with first-wins and a `--doctor` report, the reserved shell key
  table with the contexts of `N` and `P`, and the keymap check; regenerate the
  `cli-show`, `cli-api`, and `cli-api-hidden-folder` goldens
- [ ] `static/key-reveal.js` state machine with injected time and focus, and
  `static/shell-keymap.js` for the shell’s commands and targets, both in the
  `shell-tools` bundle and created and disposed with the keyboard infrastructure
- [ ] Activation paths: `selectPreviewTab()` extracted from `initTabs`, with the view
  tab bar’s `tablist` semantics, `openFilterMenu()` extracted from the filter bar with
  focus into the menu, the kept source selector handle with focus into its filter, and
  `MetabrowserPluginHost.copyFromControl()`
- [ ] Targets: Files, Commits, and Pulls tabs with fixed digits and focus hand-off, view
  tab letters registered at commit, Up (not at the root), Copy (path or revision),
  Branch, File type, and Modified within, all read again when the shell keymap is
  created
- [ ] Presentation: badge tokens and `.kbd-badge`, `inline-end` and `beside` placement
  with the file header as anchor, reveal-on-hover override, the strip’s reveal layer
  over a fixed-height host, `--text` and measured contrast on the yellow, reduced
  motion, print exclusion, and measured `REVEAL_HOLD_MS`, `REVEAL_POINTER_SLOP_PX`, and
  strip item count
- [ ] Help: View tabs, Controls, and Filters groups, bare-capital keys, no `⌘` and no
  `⇧` on any character key, and the closing Shift note
- [ ] Existing sessions and goldens: `tests/dom/preview-pane-state-session.js` and
  `cli-ui-file-lifecycle.tryscript.md` for the main tab digits, which pin
  `navigation.main-tab-destinations`, and `tests/dom/pulls-nav-session.js` and
  `cli-ui-pulls-nav.tryscript.md` for `N`, `P`, and Shift-insensitive `J` and `K`, which
  pin `github.pulls-tab-host`
- [ ] Docs: every item under “Docs updated in the same change” above: the design system
  keyboard, main tab, pull stack, and Pulls keys sections, the architecture map’s rows
  and kinds table, `development.md`, `plugins.md`, `README.md`, `e2e-testing.md`,
  `reviewing-pull-requests.md`, the QA runbook, and `CHANGELOG.md` under Unreleased

### Phase 2: Plugin Shortcut Surface

- [ ] `mb.shortcuts.attach()` and its queue in `plugin-sdk.js`, with measured eager
  bytes, and `static/plugin-shortcuts.js` in `shell-tools` for validation,
  reserved-letter refusal, `plugin`-scope registration, arbitration, replay, and detach
  by handle or abort signal plus the view-composition safety net
- [ ] Pull request page: Conversation `C`, Changes `G`, and Checks `H` through an
  exported `attachTabKeys()` that calls the page handle’s `setTab()`
- [ ] Diff view: layout toggle `L` through an exported `toggleLayout()`, badged on the
  option it would switch to, in diff files, the Git commit view, and the Changes tab
- [ ] Docs: the `docs/plugins.md` Keyboard Shortcuts subsection, SDK list, and Testing
  Checklist item; the `plugin-sdk.js` header comment; `MetabrowserSdk` in `types.d.ts`;
  the planned plugin registration surfaces row; and `CHANGELOG.md` under Unreleased
- [ ] Sessions, goldens, and the three parity rows

## Testing Strategy

### Registry and Formatter

- Letters match in both cases with and without Shift and reject Ctrl, Alt, and Meta
- A binding that requires Ctrl, Alt, or Meta is rejected at registration, for a
  character key and for a named key alike; this replaces the `Ctrl`+`F` chord fixture
- Digits match `event.key` first and `event.code` `Digit1`–`Digit9` only when nothing
  matched by key and the key is not a digit: Shift+`1` producing `!` on a US layout and
  the unshifted AZERTY digit row match by code; German Shift+`7` producing `/` is Quick
  Search, not `7`; a remapped digit row, as on Programmer Dvorak, matches the digit it
  types; Numpad digits match
- `?` and `/` remain distinct; `/` matches when typed with Shift on a German layout
- Two shell descriptors with one letter in one scope still fail; a `plugin`-scope letter
  under the same `global` letter registers and loses at dispatch
- A Shift policy on a character binding is rejected at registration
- Tree Shift+↑ and Shift+↓ still jump to the first and last row
- Formatter output for digits and the standalone `Shift` key name, no `⇧` or `⌘` in any
  character binding’s visible, spoken, or ARIA form, and `⇧` kept for the tree’s Shift+↑
  and Shift+↓
- `attachTarget()` sets and removes `aria-keyshortcuts`; a command whose targets are all
  hidden, `disabled`, `inert`, or under an ancestor with computed `display: none` leaves
  the event unhandled; the first live target in document order wins; attaching during a
  reveal mounts a badge at once; disposal leaves no badge, attribute, or record

### Main Tabs and Pull Keys

The existing sessions that pin these keys change their assertions rather than gaining
new ones:

- `tests/dom/preview-pane-state-session.js`, golden `cli-ui-file-lifecycle.tryscript.md`
  (`navigation.main-tab-destinations`):
  - `1`, `2`, and `3` open Files, Commits, and Pulls, with and without Shift, and
    Shift+`1` producing `!` opens Files;
  - `⌘1`, `⌘2`, and `⌘3` are left to the browser;
  - with Commits absent, `2` does nothing and `3` still opens Pulls;
  - the key focuses the panel’s roving row;
  - `ariaKeys` read `1`, `2`, and `3`, and Help’s spoken text names the digit alone.
- `tests/dom/pulls-nav-session.js`, golden `cli-ui-pulls-nav.tryscript.md`
  (`github.pulls-tab-host`):
  - `N` moves toward the stack top and `P` toward the base, with and without Shift;
  - an endpoint consumes the key without navigating;
  - Shift+`J` and Shift+`K` on a focused pull row or changed-file row move the row
    exactly as `J` and `K` do;
  - the Pull request stack group in Help lists `N` and `P`.
- `tests/dom/git-panel-behavior.js`, `tests/dom/tree-keyboard-navigation-behavior.js`,
  and `tests/dom/search-palette-behavior.js`: Shift with `J`, `K`, or `T` now acts.

### Reveal Session and Golden

`node tests/dom/key-reveal-session.js`, pinned by
`tests/golden/cli-ui-key-reveal.tryscript.md`, loads the production registry, reveal
module, shell keymap, and Help renderer whole, with injected time, pointer, and
visibility.
It plays the server’s side from responses the in-process application gave for
`/api/file`, `/api/git/repo`, and `/api/source/status`, recorded by its Python test the
way the source selector session’s are and listed with the golden recorders.
Each step records the machine state, the live keymap as key, command, and target, the
mounted badges, the strip’s surface and items, and Help’s groups.
Steps cover:

- a plain folder (Files only), a Git repository (Files and Commits), a repository with a
  hosted origin (Files, Commits, and Pulls), Pulls drawn before Commits is discovered
  (`1` and `3`, with `2` reserved), a mirror’s Git pin (`W`, no `A`), a Markdown file
  (`D`, `S`), a folder (`O`, `M`), an agent log (`L`, `C`, `R`), a commit view (`Y`
  copies the revision), and an HTML file with active content off (no tab keys)
- a pull request in a stack: `N` and `P` live and listed in the strip; a pull request
  outside a stack: neither
- Shift held past the threshold, then `2` with Shift still held, then release
- `?` typed as a chord, a capital letter, Shift+↑ in the tree, Shift+wheel, and a
  Shift+click with the pointer moving: no reveal; a pointer press while revealed
  dismisses it
- a retained navigation from a structured file to an agent log: the staged bar registers
  nothing, and `R` follows the committed bar
- the shell keymap created after a file, the filter bar, and the Commits tab have
  rendered, and again after a `pageshow` rebuild: the same keymap both times
- Shift in the Quick Search input: no reveal; Help open: only Help’s keys
- window blur and a lost `keyup` while revealed; a repeated `J` while revealed does not
  re-mount badges

### Keymap Check

A Python test takes each kind’s merged view list from `_views_for_kind()`, the list the
server actually serves.
For each kind it adds the always-reserved shell keys, the digits, and the contextual
shell keys whose context includes that kind, which are `N` and `P` for the pull-request
kind. It fails on a duplicate or a reserved letter.
It also compares the reserved table with the shell keys printed by the session golden.
Manifest validation tests cover a non-letter, a reserved letter, and a duplicate across
two manifests for one kind, which keeps the first key and reports the second through
`--doctor`.

### Presentation

Stylesheet-text tests pin the badge and reveal tokens as `oklch` in both themes with
`--row-flash-bg`’s hue, the zero-specificity host rule, `pointer-events: none`, the
reduced-motion rule, and the print exclusion.
The architecture map records badge placement, translucency, clipping, the strip’s upward
overlay, and contrast as a paint-exempt row, `shell.key-badge-paint`, with the QA
runbook’s browser walkthrough as evidence: both themes, 200% zoom, the minimum
navigation-pane width, a narrow viewport, and the measured hold threshold and
interaction-to-paint time.

### Parity Rows

| Aspect | Tier | Owner | Data inputs | CLI command | Golden or reason |
| --- | --- | --- | --- | --- | --- |
| `shell.key-reveal` | interaction | `static/key-reveal.js#createKeyReveal`, `static/keyboard-shortcuts.js#attachTarget`, `static/shell-keymap.js#createShellKeymap` | `/api/file`, `/api/git/repo`, `/api/source/status` | `node tests/dom/key-reveal-session.js` | `cli-ui-key-reveal.tryscript.md` |
| `shell.key-badge-paint` | paint-exempt | `static/styles.css` | `local-only` | — | Where a badge lands in its target, how much of the label shows through it, whether a scroll container clips it, its contrast as composited in each theme, and that the revealed strip overlays the tree without moving it are layout and paint. Which badges mount, and the strip’s contents, are a session owner above (`shell.key-reveal`). The tokens, the host rule, the reveal-on-hover override, reduced motion, and print are pinned by stylesheet text in `tests/test_design_vocabulary.py` and `tests/test_chrome_typography.py`; the browser walkthrough is in the v0.12 QA runbook |

Two existing rows keep their owners and change their goldens:
`navigation.main-tab-destinations` (`static/main-tabs.js#openMainTab`,
`static/main-tabs.js#bindShortcuts`) through `cli-ui-file-lifecycle.tryscript.md`, and
`github.pulls-tab-host` (`static/pulls-nav.js#registerKeys`) through
`cli-ui-pulls-nav.tryscript.md`. View keys need no row of their own: they ride the
`/api/file` envelope, whose route parity row is already covered, and the goldens named
under “Where View Keys Are Declared” print them for every multi-view kind, so a changed
key is a golden diff.
The reveal row declares its route inputs rather than `local-only`, because the live
keymap depends on the file’s views, on whether the subject is a Git repository, and on
whether the page is a mirror’s pin; the architecture map does not let `local-only` stand
in for route data.

## Acceptance Criteria

- Holding Shift alone outside a text field for the measured threshold shows a yellow
  keycap on every visible target with a live key, and releasing Shift removes them all
- `?`, capitals, Shift+Arrow, Shift+wheel, and a Shift+click made while the pointer
  moves never show a badge
- Every letter and digit shortcut behaves identically with and without Shift; a
  punctuation shortcut matches the character typed; tree Shift+↑ and Shift+↓ are
  unchanged
- No shortcut uses Cmd, Ctrl, or Alt: the registry rejects a binding that requires one,
  `⌘1`, `⌘2`, and `⌘3` are left to the browser, and neither Help nor the strip shows `⌘`
- `1`, `2`, and `3` open Files, Commits, and Pulls with or without Shift, focus the
  panel’s rows, and do nothing while their tab is absent; each visible main-pane tab
  answers to its declared letter; `O` and `M` select a folder’s Overview and Treemap
- On a pull request in a stack, `N` and `P` move toward the top and the base with or
  without Shift, and Shift+`J` and Shift+`K` move rows like `J` and `K`
- A key whose target is not visible does nothing and leaves the browser event alone
- The strip turns yellow and lists the common keys without moving the tree
- Help writes keys without Shift or Command and ends with “Press `Shift` to see relevant
  shortcut reminders.”
- The build-time keymap check fails on a duplicate view key within a kind or a reserved
  key taken by a view; in phase 2, a plugin key that is reserved is refused at
  registration and a shared one loses to the shell at dispatch
- `make verify` passes, including parity, goldens, and design vocabulary

## Rollout Plan

Each phase lands as one stack against `main`, with `CHANGELOG.md` entries under
Unreleased for the changes to released v0.12.0 keys (`⌘1` through `⌘3` removed,
Shift+`J` and Shift+`K` replaced by `N` and `P`) and for the new keys.
No alias keeps the old keys working: the server, the shell, and the built-in plugins
ship as one artifact, and no consumer outside it binds these keys.
Phase 1 is complete without phase 2: plugin-rendered tabs simply have no keys until
phase 2 lands.

## Open Questions

- **Turning character keys off.
  Decide before phase 1.** WCAG 2.1.4 asks that single-character shortcuts can be turned
  off or remapped. Phase 1 adds about a dozen, and removing `⌘1` through `⌘3` makes the
  main tabs single-character only.
  Should the Metabrowser menu gain a persisted “Single-key shortcuts” switch?
  It would add persisted state and its own parity row, so the answer changes phase 1’s
  scope.
- **A latched reveal.** Should a double tap of Shift latch the reveal until `Esc` or the
  next command, for readers who cannot hold a key and for Sticky Keys users?
  It would also make the reveal usable on a touch keyboard with a hardware Shift.
- **A main-pane focus key.** After `1` and arrow keys, reaching the main pane to scroll
  with Space takes Tab or a click.
  Is a key for “focus the main pane” worth a reserved letter?
- **Static visibility of plugin keys.** Phase 2 checks a plugin key only when it is
  attached, so the Python keymap check cannot see the diff view’s `L` or the pull
  request page’s `C`, `G`, and `H` against a kind’s view tabs.
  Should built-in plugins also declare their command keys in the manifest, so `--doctor`
  and the keymap check see every built-in key before a browser does?
  Recommended: yes, as an optional `[[shortcut]]` table validated like `[[view]] key`.
- **The Metabrowser menu.** It has no key here because `M` is Treemap and its other
  letters are taken or weak.
  Is there a letter worth reserving for it?

## References

- [Contextual keyboard help and tree navigation](../done/plan-2026-08-12-contextual-keyboard-help-and-tree-navigation.md)
- [Design system: keyboard keys](../../../design-system.md#keyboard-keys) and
  [keyboard commands and Help](../../../design-system.md#keyboard-commands-and-help)
- [Views, models, and routes](../../architecture/arch-views-models-routes.md)
- [Plugins](../../../plugins.md)
- [Reviewing pull requests](../../../reviewing-pull-requests.md)
- [WAI-ARIA `aria-keyshortcuts`](https://www.w3.org/TR/wai-aria-1.2/#aria-keyshortcuts)
- [WCAG 2.1 success criterion 2.1.4, character key shortcuts](https://www.w3.org/WAI/WCAG21/Understanding/character-key-shortcuts.html)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
