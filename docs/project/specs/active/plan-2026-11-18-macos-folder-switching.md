# Plan for Switching Folders in the macOS App

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In implementation, as a stack of four pull requests.
Epic `mb-32yq` tracks it.
The design follows a survey of `origin/main` at `a1100bca6`; the open questions at the
end took their recommended answers, under Decisions.

## Overview

The owner asked, on 2026-11-18, how the app could make it easier to open many folders
and GitHub repositories and switch between them, with many windows or with one window
that switches between the folders open now or opened lately.
They proposed making the window’s title a chooser of every open folder, since that makes
plain that it changes what this window shows, while more windows stay one command away.
Three refinements followed:

> “Let’s make sure there’s a native Mac OS-compatible indicator for how to click there
> too. Maybe a hover indicator or some other, or maybe just a tiny dropdown chevron.”

> “In general, things to do with the actual native application menus and the chrome on
> the app should be closer to native Mac OS, and things within the window should be
> closer to our native design system.”

> “But we should try to align icons and such where possible.”

This plan makes a window able to show any open folder, keeps a folder open after a
window switches away from it, makes the title a native chooser of open and recent
folders, and adds a keyboard switcher over the same list.

## Goals

- A window can switch to any open or recent folder in place, keeping its frame, Space,
  full-screen state, and place among its tabs.
- Switching back to a folder a window switched away from is instant when its page is
  still live, and never slower than reopening it.
- The title says, without a click, that it is a control: a small chevron, and a hover
  surface like a toolbar button’s.
- Many open folders stay manageable from the keyboard.
- Window chrome and menus look and behave like macOS; the page inside stays the design
  system’s; a mark that means the same thing on both sides is the same glyph.
- Native windows and tabs keep working as they do today.

## Non-Goals

- A switcher drawn by the page, in the app or in a browser tab.
  That needs a route that tells a page about the user’s other roots, which waits for the
  security model (`mb-a5ru`) and the live-server registry (`mb-5xi4`); `mb-9lf4` keeps
  it.
- A sidebar rail of folders beside the page, as Slack or Safari’s tab groups have.
  It costs the width a file tree needs, and adds a third level beside windows and tabs.
- Warm folders after their last window closes (`mb-e7im`). This plan keeps folders open
  that the user switched away from; warmth is a cache under closed folders, and stays
  that bead’s.
- A cap on servers. Background tabs have none today; the shared budget is `mb-e7im`’s,
  measured once the activity tracker’s idle cost is fixed (`mb-z46o`).

## Background

What the app does today, from
[the macOS app’s architecture](../../architecture/arch-macos-app.md):

- **A server per root.** `FolderSession` owns one `metab` server and the windows that
  show it. When its last window closes, the server stops and the folder is closed.
- **A window is one folder.** `BrowserWindowController` is created for a session and
  never changes it; it holds the web view and every piece of per-page state: the
  navigation policy, page loads, the reveal, page sheets, print, find, and downloads.
- **Windows or native tabs.** `FolderPlacement` puts a new folder in a tab of the front
  window or a window of its own.
  Every folder window shares one tabbing identifier, so AppKit’s Merge All Windows, tab
  dragging, Control-Tab, and Show All Tabs work across folders.
- **Background tabs give up their pages.** `TabDiscardPolicy` keeps the pages of the
  most recently shown background tabs, up to `defaultLiveBackgroundTabs`, and discards
  the rest; a discarded tab reloads from its running server when shown.
- **The title is the app’s own.** `TitleAccessoryController` replaces the system title
  with a leading title-bar accessory.
  Command-click and right-click on it open the folder’s path menu; a drag moves the
  window.
- **Recents come from `metab`.** File > Open Recent and the Dock menu list what
  `metab --recent --json` answers (`RecentTargetsMenu`); the
  [parity row](../../architecture/arch-parity-registry.md) `app.open-recent-menu`
  exempts only the drawing.
- **Opening an open folder brings its window forward,** as the user guide says.
- **The session is saved and restored** (`FolderWindows`, `SavedSession`). A restored
  background tab waits to start its server until it is shown (`RestoreRun`).

How other apps solve this, which the design draws on:

| App | A window is | Switching |
| --- | --- | --- |
| Finder, Xcode, VS Code | one folder or project | the Window menu, Command-\`, tabs; VS Code’s Open Recent picker, which brings a folder open elsewhere forward |
| Sublime Text | a viewer | Quick Switch Project replaces the window’s project in place |
| JetBrains IDEs, Zed | a viewer | a project picker at the start of the title bar, with “this window” or “new window” |
| Pages, TextEdit | one document | a chevron appears beside the title on hover, and a click opens a popover about the document |
| Safari, browsers | tabs | tab groups, Control-Tab, Show All Tabs |

The title-bar picker is the common answer for project tools, and a clickable title has
macOS precedent in the document apps.

## Design

### Native Chrome, Design-System Content, Shared Marks

What the app draws outside the page follows macOS; what the page draws follows
[the design system](../../../design-system.md).

| Surface | Follows | So |
| --- | --- | --- |
| Title, chevron, hover surface | macOS | an AppKit button in the title-bar accessory, the system title font, system hover |
| The chooser menu | macOS | an `NSMenu`: section headers, check marks, subtitles, Option alternates, standard keyboard and VoiceOver behavior |
| The switcher panel | macOS | an AppKit panel with a search field and a table, as File > Open URL… is a native panel |
| Everything inside the web view | the design system | unchanged by this plan |
| A mark naming a kind of root | both | one glyph, shared |

**Marks are shared where they mean the same thing.** The page draws a folder with the
Lucide `folder` glyph from `static/icons.js`. The app’s menus that list roots (the
chooser, the switcher, File > Open Recent, and the Dock menu) draw the same glyph, and a
repository the same glyph the page uses for one, as template images, so they take the
menu’s ink and highlight as an SF Symbol would.
The app loads each glyph’s SVG through `NSImage`, whose CoreSVG reads Lucide’s stroked
paths (it drops only filters, which these glyphs have none of; see
`apps/macos/AppIcon/render-svg.swift`). One table names each root kind’s Lucide id, and
a test holds the app’s copy of each glyph to its entry in `static/icons.js`, so the two
cannot drift (`RootMarkTests`, in Swift, which reads `static/icons.js` from the
checkout).
A mark with no page counterpart, such as the title’s chevron, is an SF Symbol.
The path menu keeps Finder’s own folder icons, as the system title’s path menu draws
them.

### A Window Shows One Folder at a Time, Any Folder

The window and the page come apart.

- **`FolderPage`** is a view controller that holds one folder’s web view and every piece
  of per-page state `BrowserWindowController` holds today.
  A session owns its pages, as it owns its windows today.
- **The window controller** keeps the window and its chrome: the title and mark
  accessories, the window delegate, and the menu validation that does not depend on the
  page. It shows one page at a time as its content.
- **Switching** puts another page in the window as its content view controller.
  The `NSWindow` itself never changes, so its frame, Space, full-screen state, Stage
  Manager set, minimized state, and place in its tab group all hold, which replacing one
  window with another cannot promise.
- **A page sheet** (an alert, a confirm, a print panel) is modal to its window, so a
  window with one open cannot switch; the title does not respond until the sheet ends.

### Open Folders

A folder is **open** while it is in the app’s open set, in one of two states:

- **Shown:** at least one window shows it.
- **In the background:** no window shows it, because a window switched away from it.
  Its server keeps running, and its page is kept or discarded by the same policy that
  governs background tabs: `TabDiscardPolicy` ranks pages, not windows, and a background
  folder’s page is a background page.

The transitions:

| Event | The folder it concerns |
| --- | --- |
| A window switches from A to B | A goes to the background if no other window shows it; B is shown |
| Close Window, Command-W | A folder shown in no other window closes: its server stops and it stays in Open Recent, as today |
| File > Close Folder | The folder closes everywhere: each window that showed it switches to the most recently shown background folder, or closes if there is none |
| Close Background Folders, in the chooser | Every background folder closes |
| Opening a background folder from Finder, Open With, `open -a`, or `--present` | It is placed as a newly opened folder is (`FolderPlacement`), so an agent never takes over the window the user is reading |
| Quit | Every server stops, as today |

Switching back to a background folder costs nothing when its page is live; a discarded
page reloads from the running server, as a discarded tab does.
A background folder whose server failed or stopped shows its failure when it is shown,
with Retry, as a window does today.

**The saved session** records background folders after its windows, by root path, and
the restore reopens them in the background without starting their servers; each starts
when a window first shows it, as a restored background tab does now (`RestoreRun`).
Repositories stay out of the saved session, as their tabs are today.

### The Title Is a Chooser

**The control.** The title becomes a borderless AppKit button in the same leading
accessory, showing the folder’s title as now and, after it, a small `chevron.down` SF
Symbol sized to the title font, as a pop-up button’s indicator is.
The chevron is always shown, in the tertiary label color at rest and the secondary on
hover. A document window’s title reveals its chevron only on hover, but a control that
appears only on hover cannot be found by looking, and here the title is the only way
into the menu by mouse; macOS’s own pop-up and pull-down buttons always show theirs
(Q2). On hover, the button shows a rounded surface behind the title and chevron in the
system’s fill for a control under the pointer, as a toolbar button does, which also
shows how far the control reaches.
It is drawn as the title bar’s mark draws its highlight, with the fill resolved in the
plain light or dark appearance, since a bordered button’s own hover border
(`showsBorderOnlyWhileMouseInside`) takes the title bar’s vibrant fills, which are meant
for a visual effect view to blend.
In a window that is not key, the title and chevron dim as the system title does.
The text inset, font, and truncation stay those measured for `TitleBarTitleView` on
macOS 26.5; the chevron takes its space from the title’s trailing margin, and a long
title truncates before the chevron, never under it.

**The mouse:**

- A click, released without dragging past the system’s drag threshold, opens the chooser
  under the title.
- A drag that starts on the title moves the window, as today.
- In a window that is not key, the title takes the first press, as the mark does: a drag
  moves the window and a click opens the chooser.
- Command-click and right-click open the path menu, as today.
- Outside the button, the title bar keeps the system’s double-click action.

**The keyboard and VoiceOver.** The button is a pop-up button to VoiceOver, whose value
is the title; Show Menu opens the chooser, and a custom action, Show Path, opens the
path menu.
View > Switch Folder… opens the switcher panel (below), the chooser’s keyboard
route.

**The menu:**

```text
 OPEN
 ✓ [folder] metabrowser                 ~/src/metabrowser
   [folder] notes                       ~/Documents/notes
   [repo]   kpress                      In another window
 RECENT
   [folder] fdu                         ~/src/fdu
   [repo]   owner/repo                  github.com/owner/repo
 ───────────────────────────────────────
 Open Folder…                                        ⌘O
 Open URL…                                           ⌘L
 Switch Folder…                                     ⇧⌘O
 ───────────────────────────────────────
 Close Background Folders
```

- **Open** lists every open folder, in the order the user opened them, so its rows stay
  where the hand expects them; a check mark is on this window’s folder.
  Each row’s subtitle (`NSMenuItem.subtitle`) is its location, abbreviated as the status
  view abbreviates it, or “In another window” for a folder another window shows.
- **Recent** lists `metab`’s recent targets that are not open, in `metab`’s order, as
  File > Open Recent lists them.
- The two headers are `NSMenuItem.sectionHeader(title:)`.

**What a choice does:**

| Choice | Result |
| --- | --- |
| A background folder | This window shows it |
| A folder another window shows | That window comes forward, as opening an open folder does today |
| A recent folder | It opens, and this window shows it |
| A recent repository | It opens as its link does, in a window of its own: which repository a link names is `metab`’s answer, which arrives later |
| Any folder, with Option held | It opens in a new window, placed as a new folder is; the row reads “Open … in New Window” while Option is down (`NSMenuItem.isAlternate`) |
| This window’s folder | Nothing |

In every case the folder this window showed goes to the background, unless another
window still shows it.

### The Switcher Panel

View > Switch Folder…, Command-Shift-O, opens a native panel over the front window: a
search field and a list of the same rows the chooser shows, with the same marks and
subtitles, matched by name and location as the user types.

- The list is ordered most recently shown first, with this window’s folder last, so
  Return on the first row goes back to the folder shown before this one.
- Return shows the row in this window, Option-Return in a new window, and Escape closes
  the panel; the choices do what the chooser’s do.
- Command-Delete on an open folder’s row closes that folder, so the list can be pruned
  without leaving it.

The panel is chrome: an AppKit panel, not a page, by the principle above, and it reads
the same model as the chooser, so the two never disagree.

### The Model Behind Both

`ShellCore` decides; the app target draws.

- **`OpenFolders`** holds the open set: each folder’s state, the order the user opened
  them, and when each was last shown.
  It decides each transition in the table above and which folder a window shows after a
  Close Folder.
- **`FolderChooser`** builds the rows for the chooser and the panel from `OpenFolders`,
  the window asking, and `metab`’s recent targets: which folders, in what order, which
  is checked, each row’s subtitle, and what each choice does.
- **`RootMark`** names each root kind’s Lucide id.

Each is a value type with unit tests, as `FolderPlacement`, `TabDiscardPolicy`, and
`RecentTargets` are.

### Parity

The chooser’s recent rows are `metab --recent --json`’s, in its order, already pinned by
its golden. The open rows are the app’s own live processes, which no `metab` command can
list until the registry exists (`mb-5xi4`); like the Window menu, they are platform
state, decided in `ShellCore` and pinned by its tests.
A new row in the [parity registry](../../architecture/arch-parity-registry.md),
`app.folder-chooser`, exempts the drawing of the chooser and the panel the way
`app.open-recent-menu` exempts Open Recent’s, and names `cli/recent_cli.py`. When the
registry lands, `mb-9lf4` moves the open rows’ membership to it.

## Implementation Plan

One phase, as one stack of four pull requests, layers 1 to 4 below.
Each pull request updates the user guide (`docs/macos-app.md`), the architecture
document (`arch-macos-app.md`), and `CHANGELOG.md` for what it changes.

### Phase 1: Switch Folders in a Window

- [ ] **Separate the page from the window** (layer 1, `mb-ty8k`). `FolderPage` takes the
  web view and per-page state from `BrowserWindowController`; a window shows one page.
  No behavior changes, which the existing app tests hold.
- [ ] **Open folders and switching in place** (layer 2, `mb-e9y4`). `OpenFolders` in
  `ShellCore`; switching a window’s page; background folders; File > Close Folder; the
  discard policy over pages; background folders in the saved session and its restore.
- [ ] **Shared marks** (layer 3, `mb-u08r`). `RootMark`, the glyphs as template images,
  the drift test, and Open Recent and the Dock menu drawing them.
- [ ] **The title chooser** (layer 3, `mb-4yfy`). The button with its chevron and hover
  surface, `FolderChooser`, the menu, Option alternates, and VoiceOver.
- [ ] **The switcher panel** (layer 4, `mb-boub`). View > Switch Folder…, its search,
  its order, and closing a folder from it.
- [ ] **The parity row and the hand checks** (layer 4, `mb-6ccy`). `app.folder-chooser`,
  and the chooser, hover, and switching steps in
  `docs/project/qa/qa-macos-app-hand-checks.md`.

## Testing Strategy

- **`ShellCore` unit tests:** every transition of `OpenFolders`, including Close Folder
  with and without a background folder to fall back to; the chooser’s rows, order,
  checks, subtitles, and choices; the panel’s order and matching; the discard policy
  over background pages; the saved session’s background folders surviving a save and a
  restore.
- **App tests** (beside `TabsTests`): a switch keeps the same `NSWindow`, its frame, and
  its place in a tab group; a switch back to a live page loads nothing; a switch to a
  discarded page loads once; a window with a page sheet does not switch; closing a
  window closes only folders no other window shows.
- **Live tests** against a real `metab`: switching between two folders and a repository,
  each server running once.
- **Marks:** the drift test holds each glyph to `static/icons.js`.
- **Visual,** by screenshot on macOS 26.5: the title, chevron, and hover surface in
  light and dark, key and not key, with a short and a truncated title, alone and in a
  tab group, and the open menu.
  The hover surface’s look is AppKit’s, so its check is this screenshot set, not a
  measured figure.

## Rollout Plan

The stack merges to `main` at the owner’s word, as the macOS app’s pull requests do, and
ships with the next app build.

## Decisions

The owner asked for the work end to end, so each open question below took its
recommended answer:

- **Q1:** Command-W closes the folder when no other window shows it, as a browser tab
  does.
- **Q2:** the chevron is always shown, and it is the SF Symbol `chevron.down`.
- **Q3:** File > Open Recent and the Dock menu draw the shared mark.
- **Q4:** View > Switch Folder… is Command-Shift-O.
- **Q5:** a repository’s mark is Lucide `cloud`, in the app only, since the page draws
  none.

## Open Questions

- **Q1, Command-W.** Closing a window closes a folder no other window shows, as today.
  The alternative sends it to the background, which keeps it a click away but lets the
  open list grow without the user noticing.
  Recommended: close, as a browser tab does.
- **Q2, the chevron.** Always shown and dim at rest, or revealed on hover as a document
  window’s title does?
  And an SF Symbol, as macOS’s own pop-up buttons draw, or Lucide’s `chevron-down`, as
  the page draws its chevrons?
  Recommended: always shown, and the SF Symbol, since it is chrome with no page
  counterpart beside it.
- **Q3, marks in Open Recent and the Dock menu.** They draw Finder’s folder icon today.
  Recommended: the shared mark, so the three menus that list roots match the page.
- **Q4, the switcher’s shortcut.** Command-Shift-O is free in the app’s menus and is
  Xcode’s Open Quickly; the page’s own shortcuts are single unmodified keys and
  Control-N and Control-P ([keyboard shortcuts](../../../keyboard-shortcuts.md)). Is it
  the right chord?
- **Q5, a repository’s mark.** The page draws no mark for a repository opened by its URL
  today, and the app draws a cloud.
  Which Lucide glyph should both use?

## References

- Plans: [Native macOS app](plan-2026-11-10-native-macos-app.md), whose Phase 2 and
  Phase 4 this plan builds on.
- Research:
  [Server Topology, Lifecycle, and Agent Handoff](../../research/research-2026-11-10-native-app-server-topology.md)
- Architecture: [The macOS app](../../architecture/arch-macos-app.md),
  [Recent targets](../../architecture/arch-recent-targets.md),
  [Parity registry](../../architecture/arch-parity-registry.md)
- Beads: `mb-e7im` (warm folders), `mb-z46o` (the activity tracker’s idle cost),
  `mb-9lf4` (the page’s switcher), `mb-a5ru` (the roots route), `mb-5xi4` (the registry)
- Code: `apps/macos/Sources/Metabrowser/BrowserWindowController.swift`,
  `FolderSession.swift`, `FolderWindows.swift`, `TitleAccessory.swift`,
  `RecentTargetsMenu.swift`;
  `apps/macos/Sources/ShellCore/Folders/FolderPlacement.swift`,
  `ShellCore/Web/TabDiscardPolicy.swift`; `src/metabrowser/static/icons.js`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
