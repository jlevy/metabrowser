# Feature: Files Grouping, a Diff Summary, Pull Stack Groups, and the Conversation Timeline

**Date:** 2026-11-15 (last updated 2026-11-15)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In Review

## Overview

Nine changes from the owner’s requests of 2026-11-15, a follow-up on the Files Group by
menu, a rule for tooltips, the Conversation’s rhythm and headings, a rule for commit and
pull request titles, navigation that reveals the item, label colors, Group by’s speed on
a large folder, a design-system consistency pass over all of them, a Pulls row’s two
lines, one Diff summary at a page’s top, a cached label set, and a Diff summary that
opens in the page’s flow, from the same day.
They land as one native GitHub stack of twenty-two pull requests on `main`:

1. **Menus:** one pattern for groups inside a menu, with group headings at the row
   inset, and filter menus that fit their rows and the window.
2. **Files:** a Group by menu becomes the Files tab’s main control, with Show ignored
   beside it (`mb-x1h6`), and the three filters move into the drawer.
3. **Rendered Markdown diffs:** the unchanged-blocks fold expands in place, with no
   border.
4. **Diff summary:** one collapsible tree of changed files with folder roll-ups,
   replacing the count line at the top of a multi-file diff.
5. **Pulls:** the pull requests of each native stack grouped under a “Stack #N” row,
   always on (`mb-vmwh`); rows that name no branches (`mb-ghff`) and put a member’s
   place before its number (`mb-dzsi`); one tighter slot for a row’s chevrons and icons
   (`mb-hmv7`); and pull request numbers in bold (`mb-vrvs`).
6. **Conversation and header:** a pull request’s commit rows match its comments in size
   and spacing, with a timeline line joining them (`mb-xz1r`); and its page header gives
   the branches a line of their own (`mb-fon5`), leads the row of ages with the state
   badge (`mb-4ydo`), ends the author’s row with the stack chip (`mb-cf0l`), and starts
   the title at the left edge with its number at the right (`mb-z416`).
7. **Sans headings:** an h2 in sans Markdown (chrome prose, or a document under the sans
   reading font) is upright; serif documents keep the italic.
8. **Stack keys:** Control-N and Control-P walk a pull request’s stack, freeing `N` and
   `P`, and `P` then opens the Pulls tab.
9. **Narrow toolbars:** the navigation’s toolbars and its tab bar wrap when the pane is
   too narrow for them, by one design-system rule with a set line height (`mb-nm4z`).
10. **Group by menu:** its rows read “By age” and “By file type”, as its closed trigger
    does (`mb-4mir`); `A`, `T`, and `N` choose them while it is open (`mb-ibo4`); and
    every key that opens a menu puts focus in it (`mb-spqw`).
11. **Tooltips:** the Pulls column shows no tooltips, and elsewhere a tooltip appears
    only when it adds information that is not already visible (`mb-8mpo`).
12. **Conversation rhythm and headings:** every two consecutive events are one token
    apart (`mb-w7rt`), and every event’s heading reads “author verb age”, with a chip
    only for a review state the verb does not say (`mb-novh`).
13. **Title prefixes:** a conventional-commit prefix that starts a commit’s or a pull
    request’s title, such as `feat(ledger):`, is regular weight and the rest bold,
    wherever a title appears (`mb-z57p`).
14. **Navigation reveals the item:** every route to an item reveals it in its tab
    (`mb-6y0g`).
15. **Label colors:** a pull request’s labels are colored as github.com colors them, at
    our chip’s size, with a label’s description as its tooltip (`mb-9qob`).
16. **Group by speed:** every group is read from one pass over the index (`mb-navs`),
    and a choice shows at once and while it waits (`mb-75l5`).
17. **Consistency in code:** what a design-system review of changes 1 to 16 found in
    their code and stylesheets, fixed in place (`mb-xlla`, under `mb-r5jr`).
18. **Consistency in docs:** what the same review found in the design system, the user
    docs, this plan, and the CHANGELOG, whose Unreleased block then reads as one change
    from 0.12.0 (`mb-vg55`).
19. **Pulls rows:** a Pulls row’s first line is its chevron, state icon, stack place,
    number, author, and age, and its second the whole title alone to the pane’s edge
    (`mb-lkkt`, `mb-3cbf`).
20. **Diff summary at the top:** a commit’s page and a pull request’s page each show one
    Diff summary, collapsed, at the page’s top, whose header is the counts of files and
    lines, in place of a commit’s stats block and of the summary in Changes (`mb-pb35`).
21. **Label color cache:** each repository’s whole label set is cached, so a label a
    record cached before label colors names alone is colored on first paint (`mb-varu`).
22. **Diff summary in the flow:** an opened Diff summary has no scroll bar of its own
    and grows in the page’s flow, drawing the rows in view, and its tree steps in from
    its header one `--tree-indent` a level, as nested rows do elsewhere (`mb-hi4l`).

Each change has a bead under epic `mb-eevh` that quotes the owner’s words verbatim.
This plan records the decisions that cross beads, the stack order, and what each pull
request must prove.

## Goals

- **Menus** (`mb-s6vu`, `mb-1wfn`):
  - A menu group’s heading sits at the menu’s row inset, not indented to the rows’
    labels.
  - Every menu that groups rows uses one documented pattern that plugins can reach.
  - The Files type filter menu takes its natural height, up to about 16 rows, and always
    stays inside the window.
- **Files Group by** (`mb-sogv`):
  - “Group by” leads the Files filter row, and Show ignored follows it (`mb-x1h6`). Its
    values are No grouping (the default), By age, and By file type, which read the same
    in the menu and on its closed trigger (`mb-4mir`).
  - The three filters (Modified within, File type, Minimum file size) move into the
    chevron drawer.
  - When grouping is on, the tree splits into headed sections.
    Each section holds a full tree of the items in its group, under the active filters.
  - File type groups list Documentation before Code, in the filter and in Group by
    alike.
- **Diff fold** (`mb-m5dd`): a rendered Markdown diff’s “N unchanged blocks” fold has no
  border or box, and opening it shows the hidden blocks in place.
- **Diff summary** (`mb-epw2`):
  - Every multi-file diff opens with a Diff summary, collapsed by default.
  - Its header reads like “35 changed files (2 added, 3 removed, 30 modified) +1,234
    −3,423”.
  - Opened, it is the tree of changed files the Pulls tab shows under a pull request,
    and a closed folder shows its rolled-up line counts.
- **Pull stack groups** (`mb-cm61`, `mb-vmwh`): the Pulls tab groups the pull requests
  of each native stack under a “Stack #N” row, whenever the stacks are known.
  The row is open by default and holds the stack’s pull requests, each of which still
  opens to its changed files.
- **Conversation timeline** (`mb-g3ao`):
  - Commit rows use the same type scale and spacing as the comments and reviews around
    them.
  - A timeline line joins the commits, comments and reviews, the way GitHub’s pull
    request page does.
- **Sans headings** (`mb-l4vm`): KPress italicizes `.kpress-prose h2`. That italic stays
  in serif documents, and an h2 in any sans context is upright.
  The h4 and h6 italics are unchanged.
- **Stack keys** (`mb-lnqj`): next and previous in a stack move from `N` and `P` to
  Control-N and Control-P, so the letters are free.
  The registry accepts a declared Control chord, Control alone and never from a text
  field, written `⌃N` on macOS and `Ctrl+N` elsewhere.
- **Pulls tab key** (`mb-6rfu`): `P` opens the Pulls tab by the main tabs’ own letter
  mechanism, as `F` opens Files and `H` Commits; `R` is freed.
- **Narrow toolbars** (`mb-nm4z`): in a pane too narrow for one line, every navigation
  toolbar wraps at its natural break, so no control is cut, scrolled out of reach, or
  cut short, with a line height and gap from tokens; one that fits stays one line.
- **Title prefixes** (`mb-z57p`): a conventional-commit prefix such as `feat(ledger):`
  that starts a commit’s or a pull request’s title is regular weight and the rest of the
  title keeps its weight, everywhere a title appears; any other title is unchanged.
- **Navigation reveals the item** (`mb-6y0g`): going to a file, a pull request, or a
  commit by any route switches the nav to its tab, opens the folders or stack that hold
  it, and selects and scrolls to its row.
- **Consistency** (`mb-r5jr`): every change above uses the design system’s tokens and
  shared classes, each rule is stated once in its section, no section describes a
  replaced layout, and the CHANGELOG’s Unreleased block describes each feature in its
  final state.

## Non-Goals

- **Follow-ups found in review,** which have their own beads: `mb-cz9v` (the wiki
  parser’s heading regexes), `mb-o11s` (KPress’s `:root` aliases replacing the shell’s
  font tokens), and `mb-yp9p` (commits that answer after a pull request’s Conversation
  has painted go after everything, Review comments included, rather than in time order).
- **Visual restyling** beyond what each bead names.
- **New stack data:** the stack groups use the native stack envelope the Pulls tab
  already reads (`builtin_plugins/github/pull-stacks.js`).

## Background

- **Menus:**
  - `.menu-section-label` in `static/styles.css` carries a 32 px left inset that lines a
    heading up with the row text, not with the menu’s edge.
  - `.chip-menu-panel` caps every filter menu at `max-height: 320px`, which holds about
    8 rows.
- **Files:**
  - `renderNavFilterBar` in `static/app.js` puts Modified within and File type on the
    always-visible row, and Minimum file size and Show ignored in the drawer.
  - The age options (`FILTER_RECENCY_OPTIONS`) are cumulative windows.
  - The type groups come from `data/file-rollup-format/recommended-file-types.json`, in
    the order code, docs, data, archives, media, other.
- **Diff fold:** `appendBlocks` in `builtin_plugins/diff/diff-markdown.js` folds long
  runs of unchanged blocks into a `<details>` element inside the diff’s KPress article,
  and the article’s `details` styling gives it a box.
- **Diff summary:**
  - `renderDiffToolbar` in `builtin_plugins/diff/diff-view.js` draws “N changed files +A
    −D” for every multi-file diff: a pull request’s Changes, the Git commit view, and
    diff files.
  - The Pulls tab’s tree of a pull request’s changed files is
    `builtin_plugins/github/pull-files-tree.js` (the browserless model) and
    `pull-files-view.js` (the paint).
    Its folder rows show no line counts.
- **Pull stacks:**
  - `pull-stacks.js` indexes native stacks by pull request number.
    A pull request can belong to more than one stack.
  - The Pulls rows show a stack position badge such as “2/4”.
  - Stack metadata is optional, and core pull request data never waits for it.
- **Conversation:** `pull-page.js` draws a commit event as `.github-pull-commit`
  (subject, “committed <age>”, short SHA), styled smaller and closer together than the
  comments `textBlock` draws.
  Nothing joins the timeline’s events.

## Design

### Stack Order

One native stack, linked with `gh stack link`, each pull request based on the one below
it:

| # | Branch | Beads | Why it sits here |
| --- | --- | --- | --- |
| 1 | `claude/menu-group-pattern` | `mb-s6vu`, `mb-1wfn`, this plan | The group heading pattern that pull requests 2 and 5 reuse |
| 2 | `claude/menu-groups-height` | `mb-sogv`, `mb-x1h6` | Reuses the heading pattern for the Files tree’s group headings |
| 3 | `claude/diff-fold-inline` | `mb-m5dd` | Stacked to serialize merges, with no code dependency on the layer below; shares `diff/styles.css` with pull request 4 |
| 4 | `claude/diff-summary` | `mb-epw2` | Shares the Pulls tree model with pull request 5 |
| 5 | `claude/pulls-stack-groups` | `mb-cm61`, `mb-vmwh`, `mb-ghff`, `mb-dzsi`, `mb-hmv7`, `mb-vrvs` | Groups the Pulls rows that pull request 4’s model serves |
| 6 | `claude/pull-timeline` | `mb-g3ao`, `mb-xz1r`, `mb-fon5`, `mb-4ydo`, `mb-cf0l`, `mb-z416` | Restyles the pull request page that #438 and pull request 4 change |
| 7 | `claude/sans-h2-upright` | `mb-l4vm` | Stacked to serialize merges, with no code dependency on the layer below; extends #438’s prose-face rule and Chrome session |
| 8 | `claude/keymap-ctrl-np` | `mb-lnqj`, `mb-6rfu` | Stacked to serialize merges; changes the Pulls tab’s stack keys that pull request 5 documents |
| 9 | `claude/nav-toolbar-wrap` | `mb-nm4z` | On pull request 8; wraps the Files row pull request 2 made and the Pulls toolbar pull request 5 changed |
| 10 | `claude/menu-keys` | `mb-4mir`, `mb-ibo4`, `mb-spqw` | On pull request 9; changes the Group by menu that pull request 2 adds, on the Files filter row as pull requests 4 and 9 left it |
| 11 | `claude/tooltips-substantive` | `mb-8mpo` | On pull request 10; removes the tooltips of the Pulls rows that pull request 5 draws, and hides the shell’s tips that repeat visible text, on the Files row as pull requests 9 and 10 leave it |
| 12 | `claude/conversation-rhythm` | `mb-w7rt`, `mb-novh` | On pull request 11; respaces and reheads the Conversation that pull requests 6 and 7 leave, on the page as pull request 11 leaves its tips |
| 13 | `claude/title-prefix-weight` | `mb-z57p` | On pull request 12; draws the titles of the Pulls rows, the pull request page, and its Conversation that pull requests 5, 6, 11, and 12 change |
| 14 | `claude/reveal-on-navigate` | `mb-6y0g` | On pull request 13; reveals items in the Files tree pull request 2 groups and the Pulls stack groups pull request 5 adds, and notes beside the Pulls rows pull requests 11 and 13 change |
| 15 | `claude/github-label-colors` | `mb-9qob` | On pull request 14; colors the labels of the pull request header whose title pull request 13 draws, and stores their colors in the Pulls catalog’s rows and their descriptions in the records |
| 16 | `claude/group-by-speed` | `mb-navs`, `mb-75l5` | On pull request 15; changes Group by’s server read, its prefetch, and its wait, which pull requests 2 and 10 made, beside the reveal into the Files tree that pull request 14 adds |
| 17 | `claude/ds-consistency-code` | `mb-xlla` | On pull request 16; fixes in code and stylesheets what the consistency review (`mb-r5jr`) found in pull requests 1 to 16, with each fix’s test |
| 18 | `claude/ds-consistency-docs` | `mb-vg55` | On pull request 17; brings the design system, the user docs, this plan, and the CHANGELOG to the state pull request 17 leaves |
| 19 | `claude/pulls-rows-two-lines` | `mb-lkkt` | On pull request 18; lays a Pulls row out on two lines |
| 20 | `claude/diff-summary-top` | `mb-pb35` | On pull request 19; moves the Diff summary to the top of the commit and pull request pages, under the header whose rows pull requests 13 and 19 change |
| 21 | `claude/label-color-cache` | `mb-varu` | On pull request 20; caches the label set whose colors pull request 15 draws, for the records pull request 15 left naming their labels alone |
| 22 | `claude/diff-summary-expand` | `mb-hi4l` | On pull request 21; opens the Diff summary’s tree in the page’s flow and indents it from its header, in the places pull request 20 gives it, on the rows pull request 17 shares |
| 25 | `claude/pull-header-status` | `mb-2u08` | On pull request 24 (#474); respaces the pull request header’s labels row and status line, above the Diff summary row pull request 20 adds |

- **History:** each branch merges its parent’s tip into itself, and the bottom branch
  merges `main`. Local branches that were never pushed may be rebased once to put them
  on their parent; after the first push, no rebase and no force-push.
  A fix on a lower layer reaches the layers above by merging each owning branch’s tip
  into the layer above it, bottom up, never by `gh stack rebase`.
- **Opening the stack:** the stack opens as drafts after #437 and #438 merge.
- **Merging:** pull requests merge in order, each at the owner’s word.

### Menus

- A group’s heading uses the menu’s row inset.
- A group is a heading, a separator, and its rows, in an element with `role="group"` and
  `aria-labelledby`, under one documented class.
- The type filter menu’s cap is measured from the row height rather than written as
  pixels. The menu is capped by the space between its trigger and the window’s edge,
  re-measured on open and on resize, and scrolls inside itself past that.
  The age menu keeps its natural height in any window tall enough to hold it.

### Files Group By

- **Row:** Group by, then Show ignored (`mb-x1h6`, the owner’s follow-up of 2026-11-15),
  then Clear and the chevron at the trailing edge; a Git revision has no Show ignored.
  The chevron’s badge counts only the drawer’s three filters, since the row shows Show
  ignored’s own state, and Clear resets all four, keeping the grouping.
  The row fits the default 299 px pane at its widest, measured in Chrome; in a narrower
  pane, or the system font set, it wraps ([Narrow Toolbars](#narrow-toolbars)).
- **Age groups:** disjoint bands built from the age filter’s windows: Live; then Past
  hour, Past day, Past week and Past month, each holding only what the earlier windows
  don’t; then Older. A Git revision source has no modification times, so it doesn’t offer
  By age.
- **File type groups:** the taxonomy’s groups, with Documentation before Code, then
  Data, Archives and Media in their current order, and Other last for files in no group.
  The order is defined in one place and shared by every surface that lists the groups.
  If the rollup format treats group order as part of a published contract, the order
  lives in one shared presentation place instead, and the pull request says why.
- **Sections:** sections appear in group order, and a group left empty by the filters is
  not shown. A section’s heading uses the menu group pattern and carries the group’s
  count, beside its name ([Heading Tallies](#heading-tallies)).
- **Persistence:** the choice persists the way the filter state does.
- **Keys:** the filter shortcuts keep working once the filters move into the drawer.
  Group by, on the row, is `1`, and the drawer’s filters keep their numbers whether or
  not the drawer is open; a filter’s number opens the drawer with its menu.
  With the menu open and focused, `N`, `A`, and `T` choose No grouping, By age, and By
  file type (`mb-ibo4`), in the menu’s own scope, so `T` is Quick Search everywhere
  else; the convention is one section of `docs/design-system.md`, “Keys in a Menu”.
  Every way a filter menu opens, a number or a key on its trigger, focuses its checked
  row through one path in the filter controls, and Escape gives focus back to the
  trigger (`mb-spqw`).
- **Section semantics:** a Files section takes the `.group-heading` look and names its
  section and its tree through `aria-labelledby`; it keeps the tree’s own semantics, a
  `role="tree"` per section, and takes no `role="group"`, which in a tree means a tree
  item’s children.
- **Parity:** membership, ordering and counts belong to a route or model reached through
  `metab`, with a nontrivial golden.

### Diff Fold

- The fold has no border, box or background, closed or open.
- Opening it inserts the hidden blocks in place, laid out like their neighbours.
- Lazy mounting, opening a fold from an in-page link, and the rule that a toggle never
  selects text are unchanged.
- The change is scoped to the diff; a document’s own `<details>` elsewhere keeps its
  look.

### Diff Summary

- **One component:** a diff-plugin component used by every multi-file diff host but the
  Git commit view, whose commit summary carries the totals, so the view keeps one set of
  them (docs/design-system.md, Git Commit Summary).
  It is built on the Pulls tab’s tree model, shared rather than copied, so the Pulls
  tab’s tree gains the same folder roll-ups.
- **Header:**
  - It lists only the statuses that are non-zero, in a fixed order: added, removed,
    modified, renamed, then any other status.
  - Numbers use the shell’s formatting, line counts use the existing `diff-stat-add` and
    `diff-stat-del` tokens with U+2212 as the minus sign, and “(estimated)” stays when
    the totals aren’t exact.
  - The header is the disclosure toggle, collapsed by default.
- **Tree:**
  - Folders are toggles, and a chain of single folders is drawn as one row.
  - A file row shows its status badge and line counts, and activating it jumps the diff
    to that file.
  - A closed folder shows the rolled-up line counts of everything inside it.
- **Mounting:** the tree mounts lazily on first open and has a disposal path.

### Pull Stack Groups

- **Always on** (`mb-vmwh`, the owner’s decision after review A on #450): the Pulls tab
  always groups by stack once the stacks are known, with no toolbar control.
  A Group by stack chip fit in no form at the default 299 px pane.

- **Stack rows:**
  - Each stack with at least one pull request in the current list gets a row reading
    “Stack #N”, with the number of its pull requests in its accessible name rather than
    on the row ([Heading Tallies](#heading-tallies)). The row is open by default.
  - Under it are the stack’s pull requests present in the list, in the order the pull
    request page’s stack menu uses (top of the stack first), each keeping its own toggle
    for its changed files.
  - Pull requests in no stack follow the stacks, in the list’s own order.

- **Shared membership:** a pull request in more than one stack appears once, under the
  first stack that lists it, and its place names the others.

- **Missing or stale stack data:** the list stays flat, and nothing waits for the stack
  poller.

- **Keyboard:** a stack row is a tree row, like a folder, for the Pulls keys (J, K, and
  the expand and collapse keys).

- **Parity:** grouping, ordering and membership belong to the browserless Pulls model,
  with a session and golden.

- **More of each title** (the owner’s requests after review A on #450): a Pulls row
  names no branches (`mb-ghff`); the pull request’s page keeps them.
  A stack member’s place sits before its number on the metadata line, “1/6 · #455”, with
  no stack icon of its own, so the title’s line holds only the title and the age
  (`mb-dzsi`). A tree row’s chevrons and icons share one slightly tighter slot,
  `--tree-icon-slot`, 14px where they had 16 (`mb-hmv7`). A pull request’s number is
  bold wherever it names the pull request, through one token, `--pull-number-weight`
  (`mb-vrvs`). The Pulls column shows no tooltips, and elsewhere a tooltip appears only
  when it adds information that is not already visible (`mb-8mpo`).

- **One stack design** (the owner’s added requirement): the Pulls tab’s stack groups and
  the pull request page’s stack button and menu (`pull-page.js`) share one design,
  stated once in a “Stacks” section of `docs/design-system.md`. It covers:
  - the “Stack #N” label: gray, all caps and tracked, in the label register of the stack
    menu’s heading, at the inset `mb-s6vu` sets for menu group headings;
  - the position: after its icon on the stack button, and before the number, with no
    icon, in a Pulls row (`mb-dzsi`);
  - member rows: title, position, number, and the current pull request’s mark;
  - member order;
  - links and their hover and focus states;
  - the stack button’s tip, and the accessible names that stand in for tips in the Pulls
    column, which has none (`mb-8mpo`).

  The stack group row’s header uses that label, and its hover, focus and link behavior
  match the member rows’ wherever the two do the same thing.
  Every surface that labels a stack its own way moves onto the shared classes and
  tokens. A test pins that the stack menu’s heading and the group row’s header resolve to
  the same label tokens, and that member order matches the stack menu’s.

### Conversation Timeline

- **Type:** commit rows use the timeline’s type scale, not a smaller size of their own.
  Their metadata ("committed 1d ago", the short SHA) takes the same quiet treatment as a
  comment’s.
- **Spacing:** commits and comments are spaced by one rhythm
  ([Conversation Rhythm and Headings](#conversation-rhythm-and-headings)).
- **The line:** a timeline line runs down the Conversation tab and joins every two
  adjacent events, following the structure of GitHub’s pull request page but not its
  assets or brand. It breaks wherever something that is not an event, such as Review
  comments or a note, stands between two events, so commits that answer after the
  conversation has painted, which go after everything, get a run of their own until
  `mb-yp9p` puts them in time order.
- **Docs:** the rule is stated once in `docs/design-system.md`, using existing tokens.

### Pull Request Header

The owner’s follow-ups of 2026-11-15 to pull request 6, each its own bead:

- **Branches** (`mb-fon5`): the head and base branches leave the author’s sentence for a
  line of their own under it, one line in every state.
- **State** (`mb-4ydo`): the state badge (Draft, Open, Merged, Closed) leads the row of
  ages, “[Draft] Opened 9h ago · updated …”, instead of the author’s row.
- **Stack chip** (`mb-cf0l`): the stack chip leaves the end of the labels row for the
  right end of the author’s row, under the end of the title, so a late chip lands in the
  row’s empty end: no author shift and no reserved gap.
  Where the row has no room left, the sentence is cut short at its end rather than moved
  or wrapped.
- **Title** (`mb-z416`): the title’s icon and text start at the header’s left edge and
  its number ends on the right edge, over the stack chip, for every title length; a
  short title no longer sits centred.

### Conversation Rhythm and Headings

The owner’s follow-ups of 2026-11-15 to the Conversation, pull request 12, on
`claude/conversation-rhythm`:

- **Rhythm** (`mb-w7rt`): every two consecutive events are one token apart, card to
  card, card to commit, commit to card, and commit to commit alike, a card measured by
  its border and a commit by its text, roomier than the 12 px cards had.
  It replaces `mb-xz1r`’s “at least as far” with equal.
- **Headings** (`mb-novh`): every event’s heading is the author, a plain verb, and the
  age; a boxed chip only for a review state the verb does not say (Approved, Changes
  requested, Dismissed), so a plain review is no longer boxed as “Reviewed”.

### Sans Headings

- One scoped rule in the shell’s prose styles sets h2 upright (`font-style: normal`)
  wherever the prose face is sans.
  It keys on the two places #438 points the prose hook at sans, not on each surface: its
  selectors are `.chrome-prose .kpress-prose h2` and
  `html[data-prose-font="sans"] .kpress-prose h2`. The `md-body` fallback needs no rule,
  because it sets no italic.
- An h2 keeps its size, weight and spacing; serif documents keep KPress’s italic.
- The rule is stated once in `docs/design-system.md`, beside “Serif Is for Documents”.

### Stack Keys

- Control-N and Control-P are the registry’s only chords (`CONTROL_CHORD_KEYS`). A chord
  matches Control alone, so AltGr’s Control and Alt types its character, and never in a
  text field, where macOS moves the caret with it.
- Help, the Shift strip, and badges write the chord as the platform does, read from the
  page’s navigator. The rule, and the platform limit (Chrome on Windows and Linux keeps
  Ctrl+N for a new window), is stated once, in “Control Chords” in
  `docs/design-system.md`.
- `P` is the Pulls tab’s entry in `MAIN_TABS` (`static/main-tabs.js`), reserved in
  `keymap.py`; Commits keeps `H`, since `C` is Charts’ and Conversation’s view tab key.

### Label Colors

- GitHub gives each label a `color`, six hex digits, and a `description`, in REST and
  GraphQL alike. The selected pull request’s core asks for both, the pull request’s REST
  read already had them, and the catalog’s page asks for the color alone.
  A color that is not six hex digits is kept as none, and its chip is neutral.
- The page sets github.com’s `--label-*` properties on the chip and `github/styles.css`
  states github.com’s formula once, in both themes; the rule and why it is written in
  `rgb()` and `hsl()` are in “Label Colors” in `docs/design-system.md`. The constants
  and the rounding were read from github.com’s stylesheets and rendered labels on
  2026-11-15.
- A record keeps each label as its name, color, and description, and a catalog row as
  its name and color: no row draws labels, and the header’s tooltips come from the
  record or its core, never from a row (decided in review of `mb-9qob`, 2026-11-15). A
  record raises `PULL_RECORD_PROJECTION` to 2 and the catalog `CATALOG_PROJECTION` to 3,
  so what an earlier build cached is still shown, its labels neutral, until its next
  refresh asks for it in full (a record) or the one ALL rescan rewrites it (a row).
  Both read a label an earlier projection named alone as one without a color.
- Colors cost little and descriptions a lot, measured on 2026-11-15 on the catalog’s
  page of the 100 newest pull requests.
  kubernetes/kubernetes’s (981 labels) went from 84,678 to 101,355 bytes with colors,
  where descriptions too made it 174,997, and its average stored row from 646 to 901
  bytes, where descriptions too made it 1,637. cli/cli’s (105 labels) went from 63,097
  to 64,882 bytes, and its row from 518 to 545. Every page stays at a GraphQL cost of 1.
  A row with every text at its bound is 11,079 bytes, inside the catalog’s 32 KiB row
  limit.

### Narrow Toolbars

- **The decision** (the owner, 2026-11-15, `mb-nm4z`): “on narrow screens wrap when
  narrow on the tabs” and “make sure line height on tabs is appropriate too.
  This should be a consistent design system that works everywhere.
  Tabs containers become too narrow.”
- **One rule,** stated once in `docs/design-system.md` (“Navigation Toolbars Wrap”), for
  the Files filter row, the Pulls toolbar, the Commits tally, and the tab bar.
  The rows of controls are one primitive, `.nav-toolbar-row`, with
  `--nav-toolbar-line-height` (a chip’s height) and `--nav-toolbar-gap` between lines,
  between controls, and around them.
  A row breaks between its controls in order; the trailing group (Clear and the chevron,
  Reload) moves down whole and right-aligned.
  The Commits tally wraps as text, and the tab bar between its tabs.
- **A segmented group** that its whole line cannot hold, the Pulls Show group below
  about 218 px, takes the cluster layout until it can, fitted by `filterControls.bind`,
  the one exception beside “segmented controls never wrap”.
- **Reload** in the Pulls toolbar is held to a line’s height, a chip’s, 2 px shorter.
- **Measured first** in headless Chrome at every pane width from 179 to 420 px, in both
  font sets and both themes; the break widths are in the design system and beside the
  rules in `styles.css`, for the Pulls toolbar without the Stacks chip that pull request
  5 removed.

### Title Prefixes

- **The split** (`mb-z57p`): one pure function, `titlePrefix` in `static/formatters.js`,
  finds a type of lowercase letters, an optional scope of one or more characters other
  than parentheses, an optional `!`, and the colon, at most 16 code points, followed by
  whitespace and more of the title.
  Anything else has no prefix and is drawn as before.
- **One markup, one rule:** `titleNodes` and `titleHtml` beside it put the prefix in a
  `span.title-prefix`, the SDK’s `metabrowser.titleNodes` hands its title to the same
  function, and one rule in the shell’s stylesheet sets the span’s weight from
  `--weight-normal`. No new token: the one rule is the one place the weight is set.
- **Surfaces:** a Pulls row, the pull request page’s title, its stack menu, its
  Conversation’s commits, Quick Search’s pull requests, the Commits tab’s rows, a
  commit’s page, and its tooltip.
  Quick Search has no commit results.
  A Commits tab row’s subject is regular, and keeps that weight: the prefix there looks
  as the rest does, which is reported to the owner rather than changed.
- **Records:** the rule is stated once in `docs/design-system.md`, “Titles”, beside
  “Pull Request Numbers”.
  The split is a session owner, `shell.title-prefix`, and the weights a paint exemption,
  `shell.title-prefix-weight`, read in Chrome.

### Navigation Reveals the Item

- `static/main-tabs.js` holds the rule (`revealPlan`) and the one path every route takes
  (its controller’s `reveal`): the address’s tab comes to the front, and the tab’s panel
  reveals the item. Files reveals through `app.js`’s `revealFileRow`, Pulls through
  `pulls-nav.js` and the list’s `setCurrent`, and Commits from its own landing, after it
  reads history.
- The exceptions are stated once, in “Navigation Reveals the Item” in
  `docs/design-system.md`: focus stays where the reader is; a tab’s button keeps its
  panel’s place; a step within the item shown reveals nothing; a filtered file, a pull
  request outside the list, and a commit outside the history read are named or left,
  each with its reason.
- The decisions run browserlessly in `tests/dom/nav-reveal-session.js`, pinned by
  `cli-ui-nav-reveal.tryscript.md` (`navigation.reveal-item`). The rows in view after
  each route are checked in headless Chrome (`tests/test_nav_reveal_chrome.py`,
  `navigation.reveal-item-paint`).

### Group By Speed and Feedback

The owner’s report of 2026-11-15 on pull request 12: choosing a grouping “does nothing”.
On a folder of 270,000 files, `/api/tree?group_by=type&depth=2` took 4.5 to 5.6 s warm,
against 5 ms for the ungrouped tree.

- **One pass** (`mb-navs`): the provider reads every group from one pass over the index
  at one version, through a `grouped_tree` query (`GroupedTreeQuery`) whose groups each
  answer exactly as their own filtered tree; `/api/tree?group_by=` makes one such read,
  so its output, and its golden, are unchanged.
- **Prefetch** (`mb-navs`): opening the menu asks for nothing; pressing a row, or moving
  to it with the arrow keys, asks for that grouping alone.
  Two passes at once each took twice as long as one.
- **Feedback** (`mb-75l5`): the trigger reads a choice in the frame it is made; past the
  quiet period the tree dims and the scan row reads “Grouping by file type…”; a newer
  choice or No grouping cancels the load on its way; a file change keeps a prefetched
  answer, which the choice takes and then refreshes; a refresh asked for during a
  choice’s first load waits for it; and a reveal (pull request 14) made meanwhile lands
  once the sections paint.
  In headless Chrome the trigger always read the choice at once; what the first-click
  case reproduced was the wait: a file change between the menu opening and the choice
  dropped the prefetch, each refresh during the load discarded it and began again, and
  the two prefetches the open menu ran at once each took twice as long as one.

### Diff Summary at the Top

The owner’s report of 2026-11-15: a commit showed its counts twice, once as `M`, `A`,
and `D` file counts with line totals, and once in its diff; the counts belong in the
toggleable summary, at the top of both the commit page and the pull request page, not in
the Changes tab.

- **One summary, one wording:** each page has one Diff summary, whose header’s words are
  the shared model’s (`describeChanges`); the commit summary’s change stats remain only
  in the hover summary, which has no diff.
- **Placement:** a commit’s diff draws its summary in the commit summary’s place
  (`summaryHost`), for one file too; a pull request’s page draws its own as the header’s
  last row on every tab, through the diff view’s `summary`, from the comparison the
  prefetch reads or Changes read, and its Changes diff draws none (`summary: false`).
- **Nothing moves:** the row is held at a row’s height from first paint and the
  summary’s header is one line, cut short at its end; measured in Chrome 152 from 980 to
  320 px, the summary arriving moved no row and not the tab bar.

### Diff Summary in the Flow

The owner’s request of 2026-11-15: “We should also drop the scroll bar when it expands
and make sure that when it expands, it’s indented consistently the correct amount, just
like the nested indentations.”

- **No scroll bar:** an opened tree is as tall as its rows, in the page’s flow, and
  clips only while it travels open; it draws the rows in the window’s view of it and
  `SUMMARY_ROWS_OVERSCAN` more each way, and hears the page’s scrolls.
- **No new bound:** its length is bounded by the comparison’s 2,000 files; measured in
  Chrome on synthetic patches of 106, 600, and 2,000 files, the rows showed 8 to 57 ms
  after a press, the document held at most 116 rows, and scrolling kept its frames.
- **One step a level:** the first level starts one `--tree-indent` in from the header,
  its chevron from the header’s chevron and its name from the header’s words, and each
  level one more, in a diff’s toolbar, under a commit’s identity, and in a pull
  request’s header; the rows give back the header’s inset and pull
  (`--diff-summary-header-inset`, `--diff-summary-toggle-pull`).

### Heading Tallies

The owner’s request of 2026-11-15: a Files section heading such as “Older” right-aligned
its file count; folders keep their right-aligned size totals, but a larger group’s tally
belongs beside its heading after the small bullet, and a Pulls stack’s heading needs no
tally of its pull requests, since it is obvious.

- **Beside the name:** a heading that counts what it heads sets the count after “ · ” on
  its line, through one shell primitive, `.heading-tally`: a Files Group by section’s
  heading and a pull request page’s Review comments, which had its count in parentheses
  (`mb-mcjd`). The name is cut short before the count wraps or leaves the line; the
  numeral follows the count-summary rule for numbers.
- **No tally on a stack’s row:** a Pulls stack group’s row shows its label alone, and
  its accessible name still says its size (`mb-yk0i`).

### Pull Request Header Lines

The owner’s report of 2026-11-16, on a pull request with no labels: the “Fetched just
now via GitHub CLI” line “has a lot o vertical space above it”, and “it should just be
part of the same metadata lines”.

- **Cause:** two holds of the header’s first-paint rule (the design system’s “Regions
  Keep Their Boxes”). The labels row was always there, empty and 20 px tall, so labels
  arriving would move nothing; and Refresh, a bordered `.btn` whose slot ends the status
  line on every tab, made that line 26 px.
  Measured in Chrome 152, the line stood 32 px under the row of ages, against 6 px
  between the header’s other rows.
- **The freshness line is a metadata line** (`mb-2u08`): Refresh or Fetch and Switch to
  the head are text actions, a line tall, as Browse code is, so the line is the row of
  ages’ 18 px, one 6 px gap under it.
- **No empty labels row:** a pull request with no labels has no labels row and no gap.
  The row is held only while the record is on its way, since labels come with the record
  or its core: a record with labels lands moving nothing, and one with none takes the
  row away in the one paint that changes the header and the body together.
  A label’s color, which the repository’s label set may bring later, changes no chip’s
  box.

### API Changes

- **Files Group by** needs the grouping reached through `metab`: either a parameter on
  an existing tree or recent route, or a new route.
  Its parity row and golden arrive with it.
- **The Diff summary and the pull stack groups** read data the routes already answer:
  `pull-files`, a commit’s diff totals, and the stack envelope.
  Any new field arrives with its route’s golden.
- **Labels** in `/api/plugin/github/pull` and `/api/plugin/github/pull-cores-prepare`
  become objects of name, color, and description, and in `/api/plugin/github/pulls` of
  name and color, which those routes’ goldens print.

## Implementation Plan

### Phase 1: Menu Group Pattern and Filter Menu Height (pull request 1)

- [ ] `mb-s6vu`: inventory every menu that groups rows; one group pattern at the row
  inset; document it in `docs/design-system.md` and for plugins.
- [ ] `mb-1wfn`: the type filter menu fits its rows up to about 16 and stays inside the
  window; the age menu is unchanged.

### Phase 2: Files Group By (pull request 2)

- [ ] `mb-sogv`: the Group by control, the drawer layout, age and type groups, the
  shared type order, sections, persistence, and the route or model with its golden.
- [ ] `mb-x1h6`: Show ignored on the row after Group by, and a badge that counts only
  the drawer’s filters.

### Phase 3: Diff Fold in Place (pull request 3)

- [ ] `mb-m5dd`: a borderless fold that expands in place.

### Phase 4: Diff Summary (pull request 4)

- [ ] `mb-epw2`: the shared tree model with folder roll-ups, the summary component in
  every multi-file diff host, and the Pulls tab’s tree on the same model.

### Phase 5: Pull Stack Groups (pull request 5)

- [ ] `mb-cm61`: stack rows, ordering, shared membership, fallbacks and keys, with the
  model’s session and golden.
- [ ] `mb-vmwh`: grouping always on, with no toolbar control.
- [ ] `mb-ghff`: a Pulls row names no branches; the pull request’s page keeps them.
- [ ] `mb-dzsi`: a member’s place before its number on the metadata line, with no stack
  icon on its row.
- [ ] `mb-hmv7`: one tighter slot, `--tree-icon-slot`, for a tree row’s chevrons and
  icons.
- [ ] `mb-vrvs`: a pull request’s number in bold wherever it names the pull request,
  through `--pull-number-weight`.

### Phase 6: Conversation Timeline (pull request 6)

- [ ] `mb-g3ao`: commit rows on the timeline’s type scale and spacing, and the timeline
  line joining every event.
- [ ] `mb-xz1r`: a run of commits stands at least as far from a comment as one commit
  from the next.
- [ ] `mb-fon5`: the branches on a line of their own under the author’s sentence.
- [ ] `mb-4ydo`: the state badge leads the row of ages.
- [ ] `mb-cf0l`: the stack chip at the right end of the author’s row.
- [ ] `mb-z416`: the title’s number at the header’s right edge, over the stack chip.

### Phase 7: Sans Headings (pull request 7)

- [ ] `mb-l4vm`: an upright h2 in every sans context, pinned by an h2 check added to
  #438’s Chrome session.

### Phase 8: Stack Keys (pull request 8)

- [ ] `mb-lnqj`: Control-N and Control-P walk the stack; the registry’s Control chord,
  its guards, its platform naming, and the keymap goldens, sessions, Help copy, and
  docs.
- [ ] `mb-6rfu`: `P` opens the Pulls tab; `R` is freed, and the reserved table,
  sessions, goldens, and docs say so.

### Phase 9: Narrow Toolbars (pull request 9)

- [ ] `mb-nm4z`: one wrap rule for every navigation toolbar and the tab bar, with token
  line spacing, the segmented group’s cluster fallback, and the Files, Pulls, and
  Commits Chrome tests sweeping every pane width in both font sets.

### Phase 10: The Group By Menu (pull request 10)

- [ ] `mb-4mir`: Group by’s rows read “By age” and “By file type”, as its trigger does,
  pinned in Chrome and in the Group by session’s golden.
- [ ] `mb-ibo4`: Group by’s rows take `N`, `A`, and `T` while it is open and has focus,
  shown by the Shift reveal and in Help’s Menus group, with one menu-key convention in
  the design system; the key reveal session and its golden, and a Chrome check.
- [ ] `mb-spqw`: every key that opens a menu focuses its checked row through one path in
  the filter controls, and Escape gives focus back to the trigger; the key reveal
  session and the filter controls behavior test, and a Chrome check of
  `document.activeElement`.

### Phase 11: Tooltips Add Information (pull request 11)

- [ ] `mb-8mpo`: no tooltip on a Pulls row, a stack row, or their parts; the rule stated
  once in the design system; the app’s other tooltips audited, those that repeat visible
  text removed and the owner’s decisions on the borderline ones applied; the shell shows
  a tip equal to its element’s text only while that text is cut short; checks in
  `devtools/check_tooltips.py` and the Pulls, header, and Files Chrome tests.

### Phase 12: Conversation Rhythm and Headings (pull request 12)

- [ ] `mb-w7rt`: one rhythm between every two consecutive events.
- [ ] `mb-novh`: every event’s heading reads alike.

### Phase 13: Title Prefixes (pull request 13)

- [ ] `mb-z57p`: the split and its golden session, the shared helper on every title
  surface, the one weight rule, the Chrome weights, and the docs.

### Phase 14: Navigation Reveals the Item (pull request 14)

- [ ] `mb-6y0g`: every route to an item reveals it in its tab, with one shared path, its
  exceptions in `docs/design-system.md`, a browserless session and golden, and a Chrome
  check.

### Phase 15: Label Colors (pull request 15)

- [ ] `mb-9qob`: every query that reads labels asks for their color, and a pull
  request’s for their description too; the record keeps both and the catalog’s rows the
  color, each under a raised projection; the chips are painted by github.com’s formula
  in both themes at our chip’s size, with a label’s description as its tooltip; the
  routes’ goldens print them; and a Chrome check holds a light, a dark, a very pale, and
  a colorless label to the formula and to github.com’s own computed colors.

### Phase 16: Group By Speed and Feedback (pull request 16)

- [ ] `mb-navs`: the provider’s one-pass grouped read, its conformance test against each
  group’s filtered tree, a route test that a grouping costs one read, and the prefetch
  on a pressed row or one the arrow keys reach; the measurements in the design system’s
  “Grouping the Files Tree”.
- [ ] `mb-75l5`: the trigger in the choice’s frame, the dimmed tree under the scan row’s
  words, cancelling, kept prefetches, refreshes that wait, and a reveal that lands after
  the sections paint; in the Group by session and its golden, and in the Files Chrome
  test with the grouped requests held.

### Phase 17: Consistency in Code (pull request 17)

- [ ] `mb-xlla`: each code finding of the consistency review (`mb-r5jr`) fixed in the
  layer’s code or stylesheet: existing tokens and shared classes in place of local
  literals and copies, and the menu, stack, and loading behavior the design system
  states, each with its test.

### Phase 18: Consistency in Docs (pull request 18)

- [ ] `mb-vg55`: the CHANGELOG’s Unreleased block reads as one change from 0.12.0, with
  each feature in its final state; the design system, the user docs, and this plan
  describe the stack as pull request 17 leaves it, each rule stated once with links from
  the other sections, and with no bead IDs in the design system.

### Phase 19: Pulls Rows (pull request 19)

- [ ] `mb-lkkt`: the number’s line first, “1/4 · #113 · jlevy” with the age at the row’s
  end, then the title under the age to the row’s end; the number’s line one line at
  every width, its author giving way first and its place after; measured in Chrome from
  420 to 180 px and pinned in the Pulls stacks and header Chrome tests and the
  stylesheet’s tests.
- [ ] `mb-3cbf`: the chevron and the state icon lead the first line, in their 14 px
  slots and centered on the number’s line, and the title is alone on the second, from
  the text column to the row’s end; the row stays 43 px, the stack row’s and members’
  chevrons and an open pull request’s files keep their columns; measured in the same
  Chrome tests, whose check of the glyphs’ line fails on the layout that put them on the
  title’s line.

### Phase 20: Diff Summary at the Top (pull request 20)

- [ ] `mb-pb35`: one Diff summary at the top of the commit page and of the pull request
  page, on every tab; the commit page’s stats block removed; the pull request header’s
  last row held from first paint and measured in Chrome to move nothing; pinned in the
  diff view, git panel, pull page mount, and prefetch sessions, the prefetch golden, the
  header Chrome test, and the design vocabulary.

### Phase 21: Label Color Cache (pull request 21)

- [ ] `mb-varu`: the repository’s label set is fetched once and cached per repository,
  refreshed on its age and on a name it does not hold, and a chip takes its color and
  description from it whenever its record lacks them; a `metab` route and golden, and a
  Chrome check of a bare-names record’s chip colored on first paint.

### Phase 22: Diff Summary in the Flow (pull request 22)

- [ ] `mb-hi4l`: an opened Diff summary with no scroll bar of its own, in the page’s
  flow, drawn a window at a time against the page’s scroll, measured on 106, 600, and
  2,000 files; its tree one `--tree-indent` a level in from its header in a patch’s
  toolbar, a commit’s page, and a pull request’s header; pinned in the changed-file
  rows, commit summary, and header Chrome tests and the diff view session.

### Phase 23: Heading Tallies (pull request 23)

- [ ] `mb-mcjd`: a group or section heading’s tally sits beside its name after “ · ”, on
  its line, in one shell primitive; the Files Group by sections and the Review comments
  heading take it, and folder rows keep their right-aligned totals; measured in Chrome
  at the default pane and the 180 px minimum, with the accessible names pinned.
- [ ] `mb-yk0i`: a Pulls stack group’s row shows no tally, its size kept in its
  accessible name; the stack groups’ session and golden and the stacks Chrome test
  updated.

### Phase 24: Toolbar Rule and Bold Counts (pull request 24)

- [ ] `mb-a073`: the diff’s toolbar draws no rule under the Split | Unified chooser, on
  a commit’s page, a pull request’s Changes, and a patch, where the Diff summary’s
  header is its tree’s root; the first file card’s border, 12 px below, is the one line;
  measured in Chrome on a patch and a commit’s page.
- [ ] `mb-roa9`: every count summary bolds its numbers, `.summary-number`, and keeps its
  words regular, stated once in the design system (“Count Summaries Bold Their
  Numbers”): the Diff summary’s header and fallback line, the Files totals and filter
  remark, the Commits tally, the Pulls count, a pull request’s Checks summary, and a
  commit’s files outside the folder; held without a browser per surface and in Chrome on
  the Diff summary, the Files totals and filter remark, the Commits tally, and the Pulls
  count, each number inline with its words.

### Phase 25: Pull Request Header Lines (pull request 25)

- [ ] `mb-2u08`: the freshness line is one of the header’s metadata lines, its Refresh,
  Fetch, and Switch to the head text actions, and a pull request with no labels has no
  labels row, held only while the record is on its way; measured in Chrome 152 at 560,
  420, and 360 px in both themes, with a header Chrome check that fails on the old
  layout, and pinned in the page mount session, the reserved-chrome and design
  vocabulary tests, and the design system.

## Testing Strategy

- **Parity:** follow `AGENTS.md`. Data semantics belong to a route or model reached
  through `metab`, with a golden.
  Interaction state machines run browserlessly against the production JavaScript, with a
  session and golden. Only paint stays browser-only, and each exemption names its
  behavior, why a browserless form would be dishonest, and its evidence.
- **Measurement:** measure in headless Chrome through `tests/dom/chrome-session.mjs`,
  not in the app’s built-in browser pane.
  Each pull request’s body carries its measurements, and the large-list features include
  first paint and open times measured against the current behavior.
  Before and after screenshots are kept with the local evidence and shown to the owner
  on request.
- **Red, then green:** every new test fails on `main` before its fix.
- **CI:** each pull request runs the full gate.
  Local runs are focused tests plus `make -o install lint-check`.
- **Review:** each pull request gets a senior review (review A, round 1) before it
  merges, with follow-up rounds kept proportionate.

## Rollout Plan

The pull requests ship as drafts in one native stack and merge in order at the owner’s
word.
A phase is ticked when its pull request merges, and each bead closes then, with the
merge commit in its close reason.
This plan moves to `docs/project/specs/done/` when the last pull request in Stack Order
merges.

## Open Questions

- **Stack grouping default (answered, `mb-vmwh`):** grouping is always on when the
  repository has native stack metadata, with no option to turn it off.
- **Shared membership:** should a pull request in two stacks appear under each, rather
  than once under the first?
- **Open folders in the Diff summary (answered):** an open folder shows its line counts
  too, as a Files folder keeps its size whichever way it is turned.

## References

- **Beads:** epic `mb-eevh`; `mb-s6vu`, `mb-1wfn`, `mb-sogv`, `mb-m5dd`, `mb-epw2`,
  `mb-cm61`, `mb-g3ao`, `mb-l4vm`, `mb-lnqj`, `mb-6rfu`; `mb-x1h6`, a follow-up to
  `mb-sogv`; `mb-vmwh`, `mb-ghff`, `mb-dzsi`, `mb-hmv7`, and `mb-vrvs`, follow-ups on
  pull request 5; `mb-xz1r`, `mb-fon5`, `mb-4ydo`, `mb-cf0l`, and `mb-z416`, follow-ups
  on pull request 6; `mb-nm4z`, a follow-up to `mb-x1h6`; `mb-4mir`, `mb-ibo4`, and
  `mb-spqw`, follow-ups on the Group by menu; `mb-8mpo`, the tooltips; `mb-w7rt` and
  `mb-novh`, the Conversation’s rhythm and headings; `mb-z57p`, the title prefixes;
  `mb-6y0g`; `mb-9qob`, the label colors; `mb-navs` and `mb-75l5`, Group by’s speed and
  feedback on a large folder; `mb-r5jr`, the consistency pass, with `mb-xlla` and
  `mb-vg55`; `mb-hi4l`, the Diff summary in the page’s flow; and `mb-a073` and
  `mb-roa9`, the diff toolbar’s rule and the count summaries’ bold numbers.
- **Earlier pull requests from the same round:**
  - Merged: #433 (`mb-i1wy`), #436 (`mb-jeb5`), #439 (`mb-yfxc`), #435 (`mb-42wk`), #437
    (`mb-a9be`), #438 (`mb-k838`).
  - Deferred: `mb-cz9v`, `mb-o11s`, `mb-yp9p`.
- **Project docs:**
  - [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
  - [Design system](../../../design-system.md)
  - [Development](../../../development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
