# Feature: Files Grouping, a Diff Summary, Pull Stack Groups, and the Conversation Timeline

**Date:** 2026-11-15 (last updated 2026-11-15)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In Review

## Overview

Eight changes from the owner’s requests of 2026-11-15. They land as one native GitHub
stack of eight pull requests on `main`:

1. **Menus:** one pattern for groups inside a menu, with group headings at the row
   inset, and filter menus that fit their rows and the window.
2. **Files:** a Group by menu becomes the Files tab’s main control, with Show ignored
   beside it (`mb-x1h6`), and the three filters move into the drawer.
3. **Rendered Markdown diffs:** the unchanged-blocks fold expands in place, with no
   border.
4. **Diff summary:** one collapsible tree of changed files with folder roll-ups,
   replacing the count line at the top of a multi-file diff.
5. **Pulls:** an option to group the pull requests of a native stack under a “Stack #N”
   toggle.
6. **Conversation:** a pull request’s commit rows match its comments in size and
   spacing, with a timeline line joining them.
7. **Sans headings:** an h2 in sans Markdown (chrome prose, or a document under the sans
   reading font) is upright; serif documents keep the italic.
8. **Stack keys:** Control-N and Control-P walk a pull request’s stack, freeing `N` and
   `P`, and `P` then opens the Pulls tab.

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
    values are No grouping (the default), Age, and File type.
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
- **Pull stack groups** (`mb-cm61`): the Pulls tab can group the pull requests of each
  native stack under a “Stack #N” row.
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
| 5 | `claude/pulls-stack-groups` | `mb-cm61` | Groups the Pulls rows that pull request 4’s model serves |
| 6 | `claude/pull-timeline` | `mb-g3ao` | Restyles the pull request page that #438 and pull request 4 change |
| 7 | `claude/sans-h2-upright` | `mb-l4vm` | Stacked to serialize merges, with no code dependency on the layer below; extends #438’s prose-face rule and Chrome session |
| 8 | `claude/keymap-ctrl-np` | `mb-lnqj`, `mb-6rfu` | Stacked to serialize merges; changes the Pulls tab’s stack keys that pull request 5 documents |

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
  The row fits the default 299 px pane at its widest, measured in Chrome.
- **Age groups:** disjoint bands built from the age filter’s windows: Live; then Past
  hour, Past day, Past week and Past month, each holding only what the earlier windows
  don’t; then Older. A Git revision source has no modification times, so it doesn’t offer
  Age.
- **File type groups:** the taxonomy’s groups, with Documentation before Code, then
  Data, Archives and Media in their current order, and Other last for files in no group.
  The order is defined in one place and shared by every surface that lists the groups.
  If the rollup format treats group order as part of a published contract, the order
  lives in one shared presentation place instead, and the pull request says why.
- **Sections:** sections appear in group order, and a group left empty by the filters is
  not shown. A section’s heading uses the menu group pattern and carries the group’s
  count.
- **Persistence:** the choice persists the way the filter state does.
- **Keys:** the filter shortcuts keep working once the filters move into the drawer.
  Group by, on the row, is `1`, and the drawer’s filters keep their numbers whether or
  not the drawer is open; a filter’s number opens the drawer with its menu.
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
    “Stack #N”, with the number of its pull requests.
    The row is open by default.
  - Under it are the stack’s pull requests present in the list, in the order the pull
    request page’s stack menu uses (top of the stack first), each keeping its own toggle
    for its changed files.
  - Pull requests in no stack follow the stacks, in the list’s own order.

- **Shared membership:** a pull request in more than one stack appears once, under the
  first stack that lists it, and its badge names the others.

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
  (`mb-vrvs`).

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
  - the hover tip text.

  The stack group row’s header uses that label, and its hover, focus and link behavior
  match the member rows’ wherever the two do the same thing.
  Every surface that labels a stack its own way moves onto the shared classes and
  tokens. A test pins that the stack menu’s heading and the group row’s header resolve to
  the same label tokens, and that member order matches the stack menu’s.

### Conversation Timeline

- **Type:** commit rows use the timeline’s type scale, not a smaller size of their own.
  Their metadata ("committed 1d ago", the short SHA) takes the same quiet treatment as a
  comment’s.
- **Spacing:** commits and comments are spaced consistently, with room above each run of
  commits.
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

### API Changes

- **Files Group by** needs the grouping reached through `metab`: either a parameter on
  an existing tree or recent route, or a new route.
  Its parity row and golden arrive with it.
- **The Diff summary and the pull stack groups** read data the routes already answer:
  `pull-files`, a commit’s diff totals, and the stack envelope.
  Any new field arrives with its route’s golden.

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

- [ ] `mb-cm61`: the option, stack rows, ordering, shared membership, fallbacks and
  keys, with the model’s session and golden.

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
This plan moves to `docs/project/specs/done/` when pull request 8 merges.

## Open Questions

- **Stack grouping default (answered, `mb-vmwh`):** grouping is always on when the
  repository has native stack metadata, with no option to turn it off.
- **Shared membership:** should a pull request in two stacks appear under each, rather
  than once under the first?
- **Open folders in the Diff summary (answered):** an open folder shows its line counts
  too, as a Files folder keeps its size whichever way it is turned.
  The question was: should an open folder also show its line counts?
  This plan leaves that to the implementer, kept consistent with the Files tab’s folder
  tallies.

## References

- **Beads:** epic `mb-eevh`; `mb-s6vu`, `mb-1wfn`, `mb-sogv`, `mb-m5dd`, `mb-epw2`,
  `mb-cm61`, `mb-g3ao`, `mb-l4vm`, `mb-lnqj`, `mb-6rfu`; `mb-x1h6`, a follow-up to
  `mb-sogv`.
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
