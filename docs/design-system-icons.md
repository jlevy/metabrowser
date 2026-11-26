# Icon Catalog

This is every icon Metabrowser draws, in the browser and in the macOS app, organized by
what the icon stands for.
Each row gives the icon’s name, where its drawing comes from, what it means, the one
place it is defined, the ink it takes, and its size.
An icon means one thing, and one thing has one icon, so a mark a reader learns in one
place reads the same everywhere.

[Icons and Icon Buttons](design-system.md#icons-and-icon-buttons) in the design system
sets the rules every icon follows, such as
[One Glyph Size](design-system.md#one-glyph-size); this catalog is the inventory those
rules apply to. `tests/test_icon_catalog.py` holds the tables to the code in both
directions ([The Check](#the-check)), so an icon drawn in code and missing here, or
listed here and drawn nowhere, fails the build.

## Where Icons Come From

| Source | What it is | Where it lives |
| --- | --- | --- |
| Registry | A glyph a folder’s first paint can draw | `static/icons.js`, a startup script, as `window.MetabrowserIcons`; plugins read it as `mb.icons` |
| Shell | A glyph the server writes into a page’s first paint as markup, with no script: a root’s mark, one of a set the registry would make every page pay for, or the glyph of a control the server draws, in its box from the first paint | A data file the server reads, `static/source-kind-glyphs.json`, and the macOS app’s copy of it; or `shell_glyphs.py` |
| Plugin | A glyph only one plugin draws | Beside that plugin’s code, loaded with it |
| View bundle | A glyph only a shared view helper draws | `static/plugin-sdk-views.js`, loaded on demand |
| CSS mask | A glyph a stylesheet draws as a mask over a color token | The stylesheet rule that draws it |
| Text | A character typed in markup, where the mark is typography | Each file that types it |
| Letter | A file change’s one-letter status | The status tables |
| SF Symbol | An Apple system symbol the macOS app draws, in a menu or a SwiftUI view | The Swift code that draws it |
| App glyph | A registry glyph the macOS app draws itself, from a copy of its path data that `RootMarkTests` holds to `static/icons.js` | The Swift code that holds the copy |
| App mark | The app’s own icon and its mark | `apps/macos/AppIcon/` and the code generated from it |

Drawn glyphs are [Lucide](https://lucide.dev) v1.17.0 (ISC) unless a row says otherwise,
and each definition carries a comment naming its Lucide id, which the Icon column
repeats. Every one is inline SVG that strokes or fills `currentColor`, so the element
around it sets its ink.
A CSS mask is drawn in its rule’s background color instead, which forced colors replace
with `Canvas`, the ground the glyph sits on, so each stylesheet draws its masks in
`CanvasText` there, a system color the mode keeps, and `tests/test_icon_catalog.py`
checks every rule that inks one.
Rendered Markdown draws its own chrome from KPress’s icon set, the same Lucide release
([KPress icons](https://github.com/jlevy/kpress/blob/v0.3.0/docs/kpress-icons.md)),
Mermaid diagrams’ toolbar and dialog included: in an untrusted document, whose allowlist
drops KPress’s inline sprites, KPress’s diagram controls fetch them.
One pair in the chrome is KPress’s own: a fold expander draws KPress’s table-of-contents
expand-all pair, `chevrons-up-down` and `chevrons-down-up`, from the shell’s stylesheet,
so that a fold outside a rendered document has it too, and `tests/test_icon_catalog.py`
holds the two drawings to KPress’s sprite.
It strokes them 2.5 wide, where KPress’s sprite strokes 2: the fold’s glyph stands where
a row’s chevron would, so it takes `.toggle-chevron`’s weight, and the check compares
paths, not weight.

A glyph enters the registry only when a folder’s first paint can draw it: every page
fetches the registry before it paints, so each glyph there is paid for by every folder
([asset loading tiers](project/architecture/arch-browser-shell.md#asset-loading-tiers)).
A glyph that one view or plugin alone draws lives beside that code; two registry glyphs
break this rule ([Known Departures](#known-departures)).

## Choosing an Icon

- **Use the cataloged icon for a concept.** Add an icon only for a concept no row has,
  and add its row in the same change.
- **Never choose a file’s icon by name.** Resolve it with
  `window.metabrowser.fileTypeIcon(path)`, which returns the type registry’s shape and
  the family’s color class; the tree, plugin views, the Treemap, and the File types
  table change together when a type is added.
- **A disclosure is the chevron.** A row-like target leads with the registry’s `toggle`;
  a heading-like title ends with the section-disclosure mask.
  Both point right when closed and rotate down when open
  ([One Chevron, One Row Contract](design-system.md#one-chevron-one-row-contract)).
- **A fold is the expand/contract pair, never the chevron.** A fold expander leads with
  `chevrons-up-down` while closed and `chevrons-down-up` while open, which its primitive
  draws; it does not turn ([Fold Expanders](design-system.md#fold-expanders)).
- **Ink comes from the context, never the icon.** `--muted` at rest, `--text` on hover,
  `--link` for the chosen value, and a status’s or a family’s own token where the icon
  carries one. Color is never the only signal: the shapes differ, and a name is there.
- **Size is `--icon-glyph`.** The Size column names each exception, and the rule that
  sets one says why.
- **A character is typography, not an icon.** An arrow between two names, a key cap’s
  arrow, and a menu’s check mark are characters; a control’s or an object’s mark is a
  drawn glyph.
- **Menu action arrows describe the destination.** A right arrow navigates within
  Metabrowser. An up-right arrow opens a destination externally.
  A chevron opens a menu or disclosure.
- **A pull request’s icon follows what the page knows.** Its state’s glyph where the
  state is known, the neutral `pull` mark where only its address is, and the GitHub mark
  for a View on GitHub action
  ([External GitHub Links](design-system.md#external-github-links)).
- **A root is not an ordinary folder.** The three source kinds are drawn for a root and
  never for a folder inside it, and the ordinary folder is never drawn for a root
  ([Source Kinds](#source-kinds)).
- **Some objects have no icon on purpose.** A folder row in the browser leads with its
  chevron, and a Treemap folder’s label ends in `/`. A commit is the history graph’s
  node, and a branch or a tag is a chip whose form carries its kind
  ([Branch Chips](design-system.md#branch-chips)). Search and Close are words and keys,
  and the filter drawer’s control is the chevron.

## File Formats

A format’s icon is its type family’s shape where the type registry
(`data/file-rollup-format/recommended-file-types.toml`) declares one, and its category’s
shape otherwise. The shape is the broad type and the family’s hue is the subtype
([File Types](design-system.md#file-types)). These shapes are drawn by
`.file-identity-icon`, in `--muted` or in the family’s color from its
`.file-identity-color` class, at `--icon-glyph` in an `--icon-box`, or in a tree row’s
`--tree-icon-slot`, and at `1em` of the page’s title beside a file’s name in its view
header ([View Headers](design-system.md#view-headers)).

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `fileText`, Lucide `file-text` | Registry | The PDF family’s own shape, the drawing `doc` is | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |
| `grid`, Lucide `layout-grid` | Registry | Tables: the Delimited text, Parquet, Arrow, ORC, and SQLite families | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |
| `activity`, Lucide `activity` | Registry | The Log files family | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |

## File Type Categories

Each category is a type registry group, and its `icon` is the shape every family in it
takes unless the family declares its own.
The same shape stands for the category wherever the app names one.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `alignLeft`, Lucide `align-left` | Registry | Lines of text: the Code category | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |
| `doc`, Lucide `file-text` | Registry | A page of text: the Documentation category, and so Markdown | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |
| `list`, Lucide `list` | Registry | Records: the Data category | `static/icons.js` | `--muted`, or the family’s color | `--icon-glyph` |

The Archives category takes `copy` and the Media category `monitor`, glyphs that mean
something else in the chrome ([Known Departures](#known-departures)); the Other category
takes `file`.

## Filesystem Objects

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `file`, Lucide `file` | Registry | A file no type family claims, the Other category, and what `fileTypeIcon` returns with no registry | `static/icons.js` | `--muted` | `--icon-glyph` |
| `fileSymlink`, Lucide `file-symlink` | Registry | A symbolic link in the Files tree | `static/icons.js` | `--muted` | `--icon-glyph` |

A folder is one of two things, and each has its own marks: a **root**, what a window or
a page is opened on, whose marks are [Source Kinds](#source-kinds), and an **ordinary
folder**, every folder that is not a root, whose mark is
[The Ordinary Folder](#the-ordinary-folder).

## Source Kinds

A root is one of three kinds, and each kind has one icon, the same in the browser and in
the macOS app, so a reader who learns what a mark means in one place reads it
everywhere. The kind is `kind` in `GET /api/identity` (`IdentityKind` in
`root_identity.py`), and the words for it are `kind_label` there, so the page, the app,
and `metab` say it alike:

- **Cloud mirror**, `mirror`: a repository opened by its address and read from
  Metabrowser’s own copy of it ([Open Modes](project/architecture/arch-open-modes.md)).
  Its icon is a folder with a cloud in the lower right.
- **Local Git checkout**, `git`: a folder on this computer that holds a `.git` entry,
  whatever its remote, and so a folder that has Commits and the checkout’s revisions.
  It stays a checkout while it shows one of its revisions.
  Its icon is a folder with Git’s branch.
- **Local folder**, `folder`: any other folder on this computer, a folder in no
  repository or one served exactly below a repository’s root, which has no Git features
  of its own. Its icon is a folder with a dot, the folder as a place of its own.

The kind is how the root was opened and not what is shown now, and the test for a
checkout is the cheap one, the `.git` entry (`is_checkout_root` in
`repository_context.py`), which is also how the Commits tab is drawn: Git’s own answer
comes later, and a repository Git refuses is still a checkout on disk.

Each kind’s icon is a different shape from every other kind’s and from the ordinary
folder’s ([The Ordinary Folder](#the-ordinary-folder)), so the one row that is a root
stands out among folders, wherever the two are listed together.
The cloud overlay identifies Metabrowser’s cached copy of a remote repository.
Its folder outline follows the local Git checkout’s. The cloud fits in the opening in
the outline, using artwork adapted from Lucide’s folder and cloud glyphs.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `folderDot`, Lucide `folder-dot` | Shell | A local folder, the `folder` kind: a plain folder, with no Git features | `static/source-kind-glyphs.json` | `--muted` | `--icon-glyph` |
| `folderGit2`, Lucide `folder-git-2` | Shell | A local Git checkout, the `git` kind | `static/source-kind-glyphs.json` | `--muted` | `--icon-glyph` |
| `folderCloud` | Shell | A cloud mirror, the `mirror` kind | `static/source-kind-glyphs.json` | `--muted` | `--icon-glyph` |
| `folderDot`, Lucide `folder-dot` | App glyph | A local folder, in the app’s title chooser and path menu, Switch Folder panel, Open Recent, and Dock menu | `apps/macos/Sources/ShellCore/Folders/RootMark.swift` | The menu’s, as a template image | `RootMark.menuSize` |
| `folderGit2`, Lucide `folder-git-2` | App glyph | A local Git checkout, in the same menus | `apps/macos/Sources/ShellCore/Folders/RootMark.swift` | The menu’s, as a template image | `RootMark.menuSize` |
| `folderCloud` | App glyph | A cloud mirror, in the same menus | `apps/macos/Sources/ShellCore/Folders/RootMark.swift` | The menu’s, as a template image | `RootMark.menuSize` |

**One drawing in two places.** The server draws a kind’s icon into the page: it knows
the kind when it writes the first paint and writes that one glyph, from
`static/source-kind-glyphs.json`, as inline markup, so the mark is there with no script
and no request. The glyphs are not in the icon registry, because the registry is a
startup script every page fetches before its first tree, under a gated transfer budget
(`devtools/check_startup_scripts.py`), and a page draws one of the three.
No script draws a source-kind glyph, and none holds a copy of one.
The app draws no SF Symbol for a kind: Apple’s `folder`, `icloud`, and any Git symbol
are different drawings in another stroke weight, and the three marks would then read one
way in the page and another in a menu.
So the pairing is the identity: `RootMark` holds each glyph’s elements as the file
writes them, draws them as a template image so a menu gives them its ink and highlight
as it does a symbol, and `RootMarkTests` holds every copy to the file, and the ordinary
folder’s to the registry’s.

| Kind | Words (`kind_label`) | Page glyph | macOS mark |
| --- | --- | --- | --- |
| `mirror` | Cloud mirror | `folderCloud` | `RootMark.mirror` |
| `git` | Local Git checkout | `folderGit2` | `RootMark.gitCheckout` |
| `folder` | Local folder | `folderDot` | `RootMark.plainFolder` |

**What each tooltip says.** A mark is glyph-only, so its tooltip and its accessible name
are one sentence that names the kind and what it is of (`kind_tip` in
`GET /api/identity`): “Cloud mirror of owner/repo”, “Local Git checkout (GitHub:
owner/repo)”, and “Local folder”.
The repository is the one the provider or the checkout’s `origin` names on github.com,
spelled as its owner spells it.
A checkout whose `origin` is elsewhere, or that has none, and a mirror no provider
knows, say the words alone: a mirror’s own address is the source’s as given, which a
route may say only where `tests/test_serve_pin.py` allows.

**Where each is drawn.**

| Surface | Draws |
| --- | --- |
| The navigation column’s heading, before the root’s name | The root’s kind mark, `.header-root-kind`, at `--icon-glyph` in `--muted`, inside the Home link and next to the Info button for folder details. The server writes the kind, its glyph, and its sentence into the first paint (`source_kind_marks.py`) |
| The main pane’s header for the root, at the title’s size | The same mark: the glyph is copied from the navigation’s (`view-header.js`, `folderGlyphHtml`), so a root’s name has one icon wherever it stands. A pinned revision of a checkout, whose root is still the root, keeps it. A folder inside the root leads with the ordinary folder |
| The macOS title’s folder chooser and the Switch Folder panel, each row | The row’s kind mark, from its window’s `/api/identity` or its recent entry |
| File > Open Recent and the Dock menu, each row | The row’s kind mark, from the entry’s `mode` and `git` in `metab --recent --json`, never from a look at the folder, which can raise a privacy prompt |
| The macOS title’s path menu | The root’s kind mark on its first row, and the ordinary folder on each row for a folder above it |

## The Ordinary Folder

A folder that is not a root is an ordinary folder, and its icon is the plain outline.
Closed and open are the family’s two states, and each is its own Lucide drawing:

- **Closed, `folder`**: a folder other than the root in a view header, beside its name,
  and a folder above a root in the app’s path menu.
  It is the one ordinary folder drawn today.
- **Open, Lucide `folder-open`**: a folder whose contents show.
  No surface draws it today: a folder’s row in the browser leads with its chevron, which
  says open or closed, and its view header is closed.
  The icon joins the registry, with its row here, when the first row needs it.

An ordinary folder never takes a root’s icon and a root never takes the ordinary one:
`folder` is no kind’s glyph, and no source-kind glyph is a folder’s.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `folder`, Lucide `folder` | Registry | An ordinary folder, closed: a folder other than the root, beside its name in its view header | `static/icons.js` | `--muted` | `1em` of the page’s title |
| `folder`, Lucide `folder` | App glyph | An ordinary folder, a row above the root in the app’s title path menu | `apps/macos/Sources/ShellCore/Folders/RootMark.swift` | The menu’s, as a template image | `RootMark.menuSize` |

In the browser a folder’s row leads with its chevron and a Treemap folder’s label ends
in `/`, so neither draws a folder icon.

## Git and GitHub Objects

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `gitPullRequest`, Lucide `git-pull-request` | Plugin | An open pull request | `builtin_plugins/github/pull-state.js` | `--github-pull-open` | `--icon-glyph` in a row; `1em` of the page’s title |
| `gitPullRequestDraft`, Lucide `git-pull-request-draft` | Plugin | A draft pull request | `builtin_plugins/github/pull-state.js` | `--github-pull-draft` | `--icon-glyph` in a row; `1em` of the page’s title |
| `gitMerge`, Lucide `git-merge` | Plugin | A merged pull request | `builtin_plugins/github/pull-state.js` | `--github-pull-merged` | `--icon-glyph` in a row; `1em` of the page’s title |
| `gitPullRequestClosed`, Lucide `git-pull-request-closed` | Plugin | A closed pull request | `builtin_plugins/github/pull-state.js` | `--github-pull-closed` | `--icon-glyph` in a row; `1em` of the page’s title |
| `arrowLeft`, Lucide `arrow-left` | Plugin | Guided Review’s previous step, in the step list’s head and before the way back below a step | `builtin_plugins/github/guided-review.js` | The button’s | `--icon-glyph` |
| `arrowRight`, Lucide `arrow-right` | Plugin | Guided Review’s next step, in the step list’s head and after the way on below a step | `builtin_plugins/github/guided-review.js` | The button’s | `--icon-glyph` |
| `pull`, Lucide `git-pull-request` | View bundle | A link to a pull request whose state the page does not know, and the link card of one whose data gives none, which asks `decorateExternalLink` for it | `static/plugin-sdk-views.js` | The link’s; the tooltip’s muted ink in a link card (`.link-card-mark`) | `--icon-glyph`; smaller in a rendered document (`.kpress .external-link-icon`) |
| `issue`, Lucide `circle-dot` | View bundle | A link to a GitHub issue | `static/plugin-sdk-views.js` | The link’s | `--icon-glyph`; smaller in a rendered document (`.kpress .external-link-icon`) |
| `github`, Octicons `mark-github-16` | View bundle | GitHub: the View on GitHub button’s mark, and a link to any other GitHub page | `static/plugin-sdk-views.js` | The link’s | `--icon-glyph`; smaller in a rendered document (`.kpress .external-link-icon`) |
| `arrowRight`, Lucide `arrow-right` | View bundle | Navigate within Metabrowser from a menu, including View This Branch, View This Tag, and View PR Head in Metabrowser | `static/plugin-sdk-views.js` | `--muted` | `--icon-glyph` in `.menu-item-icon` |
| `arrowUpRight`, Lucide `arrow-up-right` | View bundle | Open in Browser and Open on GitHub menu actions | `static/plugin-sdk-views.js` | `--muted` | `--icon-glyph` in `.menu-item-icon` |
| `layers`, Lucide `layers` | Registry | A stack of pull requests: a stack’s row, the page’s stack button, another stack a member is in, and a link card’s stack | `static/icons.js` | `--muted` on a row, the button’s text ink on the stack button, the tooltip’s muted ink in a link card | `--icon-glyph`; the text’s `1em` in a member’s place |
| `PERSON_GLYPH`, Lucide `circle-user-round` | View bundle | A person with no avatar, in an actor identity’s box | `static/plugin-sdk-views.js` | `--muted` | `--actor-avatar-size`, the avatar it stands in for |

A pull request’s state glyph is one module’s, `pullStateIcon` in `pull-state.js`, so a
Pulls row and its page cannot disagree
([A Pull Request’s State](design-system.md#a-pull-requests-state)). The neutral `pull`
mark is the open state’s drawing without the state’s color.
A link card draws a pull request’s mark as `decorateExternalLink` draws it on the pull
request’s address, with the state’s glyph only where the card’s data gives the state
([Tooltips on Links](design-system.md#tooltips-on-links)).

## Status and Change Marks

A file’s change is a letter, not a glyph: it replaces the file’s icon in a changed-files
tree and is the letter in a count such as “10 A, 5 D, 4 M”
([File Change Status](design-system.md#file-change-status)). The letter and the status’s
accessible name carry the meaning without the color.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `A` | Letter | Added | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-added` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `C` | Letter | Copied | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-added` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `D` | Letter | Deleted | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-deleted` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `M` | Letter | Modified | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-modified` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `T` | Letter | Type changed | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-modified` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `R` | Letter | Renamed | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-renamed` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |
| `U` | Letter | Unmerged | `static/changed-files-tree.js`, `builtin_plugins/diff/diff-model.js` | `--git-status-deleted` | `--ui-small-font-size`, in a tree row’s `--tree-icon-slot` |

An ignored entry has no mark: its whole row, icon included, is dimmed to
`--dimmed-content-opacity` and keeps its family’s hue.

When the macOS app’s server cannot serve a folder, the app’s failure screen leads its
heading with Apple’s warning triangle.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `exclamationmark.triangle.fill` | SF Symbol | The server could not serve the folder: the heading of the app’s failure screen | `apps/macos/Sources/Metabrowser/StatusView.swift` | Its own colors, as a multicolor symbol | The heading’s `.title3` font |

Settings > Check Setup leads its verdict with a mark for the whole report.
The verdict’s sentence carries the meaning without the color, and the report below it
names each check’s state in words.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `checkmark.circle.fill` | SF Symbol | No problems: `metab` can serve a folder with this setup, in Settings > Check Setup | `apps/macos/Sources/Metabrowser/CheckSetupPane.swift` | SwiftUI’s `.green` | The verdict’s `.headline` font |
| `xmark.octagon.fill` | SF Symbol | A problem: `metab` cannot serve a folder until it is fixed, in Settings > Check Setup | `apps/macos/Sources/Metabrowser/CheckSetupPane.swift` | SwiftUI’s `.red` | The verdict’s `.headline` font |

Each Settings tab shows a symbol above its title in the window’s toolbar.
The title carries the meaning; the symbol only marks the tab.

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `gearshape` | SF Symbol | Settings > General | `apps/macos/Sources/Metabrowser/SettingsWindow.swift` | AppKit’s toolbar ink for a template image | AppKit’s preference-style toolbar item |
| `terminal` | SF Symbol | Settings > Runtime: the `metab` command the app runs | `apps/macos/Sources/Metabrowser/SettingsWindow.swift` | AppKit’s toolbar ink for a template image | AppKit’s preference-style toolbar item |
| `puzzlepiece.extension` | SF Symbol | Settings > Plugins | `apps/macos/Sources/Metabrowser/SettingsWindow.swift` | AppKit’s toolbar ink for a template image | AppKit’s preference-style toolbar item |
| `stethoscope` | SF Symbol | Settings > Check Setup: the setup report | `apps/macos/Sources/Metabrowser/SettingsWindow.swift` | AppKit’s toolbar ink for a template image | AppKit’s preference-style toolbar item |

## UI Chrome and Actions

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `toggle`, Lucide `chevron-right` | Registry | Show or hide what a row holds: tree folders and containers, the tally tree, diff file bars, the Diff summary, Pulls rows, agent log events, the filter drawer, and menu triggers. In menus it points down and stays fixed while open. Never a fold expander’s, which draws the pair below | `static/icons.js` | Muted gray at rest, stronger neutral ink on interaction | Centered in its target. A ref chip’s action cue overlays its trailing edge. The Files revision row uses one standalone chevron for the chooser |
| `info`, custom circled i | Registry | Open folder details from the navigation heading | `static/icons.js` | `--muted` at rest, `--text` on interaction | `--icon-glyph` in the shared icon-button target |
| `chevron.down` | SF Symbol | A window’s title opens its folder chooser | `apps/macos/Sources/Metabrowser/TitleAccessory.swift` | Secondary label color at rest, primary on hover or open, tertiary in an inactive window | Seven tenths of the title font’s point size, centered vertically |
| `checkmark` | SF Symbol | The folder this window shows, in the Switch Folder panel’s list | `apps/macos/Sources/Metabrowser/SwitchFolderWindow.swift` | Secondary label color, or the selection’s ink on the selected row | The row’s default symbol size |
| `checkmark` | SF Symbol | The folder this window shows, in the title’s folder chooser: AppKit’s own check mark for a menu item’s state, redrawn into a taller image so that it stands on the name’s line of a two-line row, beside the row’s mark | `apps/macos/Sources/ShellViews/TitleLineMenuItem.swift` | The menu’s ink and highlight, as a template image | The menu font’s 13 points, bold, small: AppKit’s own check, drawn at its size |
| `.section-disclosure-trigger::after`, Lucide `chevron-right` | CSS mask | Show or hide a section, after its heading, and a rendered document’s `summary` | `static/styles.css` | `--section-disclosure-chevron-color` | `--section-disclosure-chevron-size`, in `em` of the heading |
| `.fold-expander::before`, Lucide `chevrons-up-down` | CSS mask | Expand: a closed fold expander opens the content it withholds, in place. KPress’s table-of-contents expand-all glyph | `static/styles.css` | `--muted`, the expander’s ink, at rest; `--text` under the pointer or the focus ring | `--toggle-chevron-size`, leading the expander’s label where a chevron would |
| `.fold-expander[aria-expanded="true"]::before`, Lucide `chevrons-down-up` | CSS mask | Contract: an open fold expander, a button’s `aria-expanded` or a native summary’s `details[open]`, folds its content back. KPress’s table-of-contents collapse-all glyph | `static/styles.css` | As `chevrons-up-down` | As `chevrons-up-down` |
| `.mb-image-fallback::before`, Lucide `image` | CSS mask | An image a rendered document’s page does not load, drawn before its alt text | `static/styles.css` | The link’s own ink (`currentcolor`) | `1.1em` of the chip’s text |
| `copy`, Lucide `copy` | Registry | Copy an identifier or a block’s content to the clipboard; also the Archives category’s shape | `static/icons.js` | `--muted` at rest, `--text` on hover | `--icon-glyph` |
| `print`, Lucide `printer` | Registry | Print the document | `static/icons.js` | `--muted` at rest, `--text` on hover | `--icon-glyph` |
| `gear`, Lucide `settings` | Registry | Open the Metabrowser menu | `static/icons.js` | `--muted` at rest, `--text` on hover | `--icon-glyph` |
| `REFRESH_SVG`, Lucide `rotate-cw` | Shell | Refresh: the navigation’s one Refresh, at the top of the navigation pane just before the Metabrowser menu’s gear on every page, which refreshes what the page shows, the parts on screen first; the server writes it into the page with its button | `shell_glyphs.py` | `--muted` at rest, `--text` on hover; dimmed while it waits | `--icon-glyph` |
| `monitor`, Lucide `monitor` | Registry | The system theme, in the menu’s theme chooser; also the Media category’s shape | `static/icons.js` | `--muted`, `--link` when chosen | One step over `--icon-glyph`: a segment’s glyph is its whole label (`.menu-seg svg`) |
| `sun`, Lucide `sun` | Registry | The light theme | `static/icons.js` | `--muted`, `--link` when chosen | One step over `--icon-glyph`, as `monitor` |
| `moon`, Lucide `moon` | Registry | The dark theme | `static/icons.js` | `--muted`, `--link` when chosen | One step over `--icon-glyph`, as `monitor` |
| `serif`, bespoke | Registry | The serif reading font: an “A” in the generic serif family | `static/icons.js` | `--muted`, `--link` when chosen | One step over `--icon-glyph`, as `monitor` |
| `sans`, bespoke | Registry | The sans reading font: an “A” in the generic sans-serif family | `static/icons.js` | `--muted`, `--link` when chosen | One step over `--icon-glyph`, as `monitor` |
| `↑` | Text | The parent folder, in the parent navigation button | `static/view-header.js`, `builtin_plugins/folder/treemap.js` | `--muted` | `--ui-small-font-size` |
| `✓` | Text | A chosen value in a filter chip’s menu | `static/filter-controls.js` | `--link`, in `.chip-menu-check` | The text’s, in a fixed column |
| `→` | Text | From one to the other: a rename, a mode or type change, and a merge’s source and target | `builtin_plugins/diff/diff-model.js`, `static/git-panel.js`, `static/plugin-sdk-views.js` | The text’s | The text’s |
| `→` | Text | A SQLite foreign key from its columns to the referenced table | `builtin_plugins/sqlite/tables-model.js` | The text’s | The text’s |
| `→` | Text | An agent log’s tool call, going out, in an event’s kind | `builtin_plugins/agents/agent-log.js` | The kind badge’s | The text’s |
| `←` | Text | An agent log’s tool result, coming back, in an event’s kind | `builtin_plugins/agents/agent-log.js` | The kind badge’s | The text’s |
| `↑` | Text | A session table’s sorted column, ascending, after its header’s label | `builtin_plugins/agents/agents-views.css` | The header’s | The header’s |
| `↓` | Text | A session table’s sorted column, descending, after its header’s label | `builtin_plugins/agents/agents-views.css` | The header’s | The header’s |
| `→` | Text | The Metabrowser menu title’s link to the project on GitHub, shown on hover | `server.py` | The title’s | The text’s |
| `⏎` | Text | A line with no newline at its end, in a diff | `builtin_plugins/diff/diff-view.js` | `--muted` | The text’s |
| `‹` | Text | Opens the hex code the binary view shows for a byte that is not printable ASCII, such as `‹FF›` | `builtin_plugins/binary/byte-format.js` | `--muted`, the code’s | `--mono-block-font-size`, the code block’s |
| `›` | Text | Closes a byte’s hex code in the binary view | `builtin_plugins/binary/byte-format.js` | `--muted`, the code’s | `--mono-block-font-size`, the code block’s |
| `☰` | Text | The table of contents toggle in an untrusted document’s render | `builtin_plugins/markdown/inert-toc.js` | KPress’s muted document ink | The text’s |
| `↑` | Text | A table column sorted ascending, after its header’s label | `builtin_plugins/table/table-view.js` | `--link` | The header’s |
| `↓` | Text | A table column sorted descending, after its header’s label | `builtin_plugins/table/table-view.js` | `--link` | The header’s |
| `▾` | Text | A table column’s menu, to sort, filter, or hide it, after its header’s label | `builtin_plugins/table/table-view.js` | The header’s, `--text` on hover | The header’s |
| `×` | Text | Removes a table’s filter, at the end of its chip | `builtin_plugins/table/table-view.js` | `--muted`, `--text` on hover | The chip’s |
| `←` | Text | Back to the table, before a record’s link | `builtin_plugins/table/table-view.js` | The link’s | The link’s |

### Keyboard Hints

A key is a `.kbd` key cap, and the shared shortcut formatter writes its label, so a
caller never types an arrow or a modifier itself
([Keyboard Keys](design-system.md#keyboard-keys)).

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `⌃` | Text | The Control key, in a Control chord | `static/keyboard-shortcuts.js` | The key cap’s | The key cap’s |
| `↑` | Text | The Up arrow key | `static/keyboard-shortcuts.js` | The key cap’s | The key cap’s |
| `↓` | Text | The Down arrow key | `static/keyboard-shortcuts.js` | The key cap’s | The key cap’s |
| `←` | Text | The Left arrow key | `static/keyboard-shortcuts.js` | The key cap’s | The key cap’s |
| `→` | Text | The Right arrow key | `static/keyboard-shortcuts.js` | The key cap’s | The key cap’s |

## The App’s Own Marks

| Icon | Source | Meaning | Defined in | Ink | Size |
| --- | --- | --- | --- | --- | --- |
| `metabrowser-icon` | App mark | The macOS app’s icon: the MB mark on its squircle | `apps/macos/AppIcon/metabrowser-icon.json` | Its own fills, citrine and amethyst | The `.icns` sizes `scripts/build-icon.sh` writes |
| `metabrowser-icon-dev` | App mark | A development build’s icon, with a gold rim | `apps/macos/AppIcon/metabrowser-icon-dev.json` | Its own fills | The `.icns` sizes `scripts/build-icon.sh` writes |
| `AppIconMark` | App mark | The mark alone, in the app’s title bar | `apps/macos/Sources/ShellCore/App/AppIconMarkGeometry.swift` | `AppIconMark.titleBarFills`, for the title bar’s appearance | The title bar’s height |
| `metabrowser-icon.png` | App mark | The README’s icon, the release icon at one size | `images/metabrowser-icon.png` | Its own fills | Its pixels |

[Metabrowser App Icon](../apps/macos/AppIcon/README.md) has the design and how to
regenerate every one of these from the masters.

## Known Departures

Each of these breaks a rule above, and is listed so that nobody copies it.

- **Two category shapes mean something else in the chrome.** The Archives category takes
  `copy`, the clipboard action, and the Media category takes `monitor`, the system
  theme.
- **One drawing, two names.** The PDF family declares `fileText`, which is the drawing
  `doc` is, the Documentation category’s shape that PDF would take anyway.
- **A character stands in for a drawn glyph.** An untrusted document’s table of contents
  toggle types `☰` where a trusted render draws KPress’s Lucide `list`.
- **The Metabrowser menu’s GitHub link ends in `→`**, where a link to GitHub elsewhere
  carries the GitHub mark.
- **Two glyphs one plugin draws are in the registry.** Only the GitHub plugin draws
  `layers`, and only the Markdown plugin’s print button draws `print`, yet both are
  registry glyphs that every folder’s startup pays for.
  `print` stayed when the print button moved from the shell’s header into a rendered
  document.
- **The app’s failure screen draws its warning triangle in color.**
  `exclamationmark.triangle.fill` renders in Apple’s multicolor yellow, where every
  other symbol takes its menu’s template ink and every other glyph `currentColor`.
- **The browser’s tab shows no icon of the app’s own.** The page names no favicon, so
  the browser asks for `/favicon.ico` and draws its default.

## The Check

`tests/test_icon_catalog.py` reads the tables above, the rows under the header “Icon,
Source, Meaning, Defined in, Ink, Size”, and holds them to the code:

- the registry’s glyphs are the Registry rows, every one has a caller, and every name a
  caller or the type registry asks for is one of them;
- every other SVG glyph a browser source defines by name is a Plugin or View bundle row
  in the file that defines it, every SVG a browser source draws is one it defines by
  name, and the server’s page draws none;
- every glyph character a browser source or the server’s page types, as itself or as an
  escape, is a Text row with exactly the files that type it, except in a comment or a
  console message;
- the stylesheets’ masked glyphs, the SF Symbols the macOS app draws in AppKit or
  SwiftUI, and the change letters of both status tables, which must agree, are rows;
- the source kinds are the identity route’s `kind` values, each with its own glyph in
  the glyph file and one Shell row, the four drawings, the ordinary folder’s included,
  differ, no script or stylesheet holds a copy of one, the ordinary folder has only the
  callers the catalog names, and the app’s `RootMark` holds the same glyphs and the same
  words as the page ([Source Kinds](#source-kinds));
- two rows naming one upstream glyph draw it the same, and a row’s Lucide id is the one
  its definition’s comment names;
- a registry row names each category and family that takes its shape, and the type
  registry’s schema permits exactly the shapes its categories and families take;
- every token a row’s ink or size names is declared by a shipped stylesheet.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
