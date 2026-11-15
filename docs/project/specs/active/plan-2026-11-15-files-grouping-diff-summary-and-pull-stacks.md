# Feature: Files Grouping, a Diff Summary, Pull Stack Groups, and the Conversation Timeline

**Date:** 2026-11-15 (last updated 2026-11-15)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft

## Overview

Six changes from the owner’s requests of 2026-11-15. They land as one native GitHub
stack of six pull requests on `main`:

1. **Menus:** one pattern for groups inside a menu, with group headings at the row
   inset, and filter menus that fit their rows and the window.
2. **Files:** a Group by menu becomes the Files tab’s main control, and the three
   filters move into the drawer.
3. **Rendered Markdown diffs:** the unchanged-blocks fold expands in place, with no
   border.
4. **Diff summary:** one collapsible tree of changed files with folder roll-ups,
   replacing the count line at the top of a multi-file diff.
5. **Pulls:** an option to group the pull requests of a native stack under a “Stack #N”
   toggle.
6. **Conversation:** a pull request’s commit rows match its comments in size and
   spacing, with a timeline line joining them.

Each change has a bead under epic `mb-eevh` that quotes the owner’s words verbatim.
This plan records the decisions that cross beads, the stack order, and what each pull
request must prove.

## Goals

- **Menus** (`mb-s6vu`, `mb-1wfn`):
  - A menu group’s heading sits at the menu’s row inset, not indented to the icon or
    check column.
  - Every menu that groups rows uses one documented pattern that plugins can reach.
  - The Files type filter menu takes its natural height, up to about 16 rows, and always
    stays inside the window.
- **Files Group by** (`mb-sogv`):
  - “Group by” is the only control on the Files filter row.
    Its values are No grouping (the default), Age, and File type.
  - The three filters (Modified within, File type, Minimum file size) and Show ignored
    move into the chevron drawer.
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

## Non-Goals

- **Follow-ups found in review,** which have their own beads: `mb-cz9v` (the wiki
  parser’s heading regexes) and `mb-o11s` (KPress’s `:root` aliases replacing the
  shell’s font tokens).
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
| 1 | `claude/menu-group-pattern` | `mb-s6vu`, `mb-1wfn`, this plan | The group heading pattern that pull requests 2, 4 and 5 reuse |
| 2 | `claude/menu-groups-height` | `mb-sogv` | Reuses the heading pattern for the Files tree’s group headings |
| 3 | `claude/diff-fold-inline` | `mb-m5dd` | Shares `diff/styles.css` with pull request 4 |
| 4 | `claude/diff-summary` | `mb-epw2` | Shares the Pulls tree model with pull request 5 |
| 5 | `claude/pulls-stack-groups` | `mb-cm61` | Groups the Pulls rows that pull request 4’s model serves |
| 6 | `claude/pull-timeline` | `mb-g3ao` | Restyles the pull request page that #438 and pull request 4 change |

- **History:** each branch merges its parent’s tip into itself, and the bottom branch
  merges `main`. Local branches that were never pushed may be rebased once to put them
  on their parent; after the first push, no rebase and no force-push.
- **Opening the stack:** the stack opens as drafts after #437 and #438 merge.
- **Merging:** pull requests merge in order, each at the owner’s word.

### Menus

- A group’s heading uses the menu’s row inset.
- A group is a heading, a separator, and its rows, in an element with `role="group"` and
  `aria-labelledby`, under one documented class.
- The type filter menu’s cap is measured from the row height rather than written as
  pixels. The menu is capped by the space between its trigger and the window’s edge,
  re-measured on open and on resize, and scrolls inside itself past that.
  The age menu keeps its size.

### Files Group By

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
  The keyboard shortcuts that open or badge the filter menus keep working once those
  menus move into the drawer.
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

- **One component:** a diff-plugin component used by every multi-file diff host.
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

- **The option:** a control in the Pulls tab’s toolbar groups the list by stack.
  The choice persists.
- **Stack rows:**
  - Each stack with at least one pull request in the current list gets a row reading
    “Stack #N”, with the number of its pull requests.
    The row is open by default.
  - Under it are the stack’s pull requests present in the list, in stack order, each
    keeping its own toggle for its changed files.
  - Pull requests in no stack follow the stacks, in the list’s own order.
- **Shared membership:** a pull request in more than one stack appears once, under the
  first stack that lists it, and its badge names the others.
- **Missing or stale stack data:** the list stays flat, the option says why, and nothing
  waits for the stack poller.
- **Keyboard:** a stack row is a tree row, like a folder, for the Pulls keys (J, K, and
  the expand and collapse keys).
- **Parity:** grouping, ordering and membership belong to the browserless Pulls model,
  with a session and golden.

### Conversation Timeline

- **Type:** commit rows use the timeline’s type scale, not a smaller size of their own.
  Their metadata ("committed 1d ago", the short SHA) takes the same quiet treatment as a
  comment’s.
- **Spacing:** commits and comments are spaced consistently, with room above each run of
  commits.
- **The line:** a timeline line runs down the Conversation tab and joins every event,
  following the structure of GitHub’s pull request page but not its assets or brand.
- **Docs:** the rule is stated once in `docs/design-system.md`, using existing tokens.

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

## Testing Strategy

- **Parity:** follow `AGENTS.md`. Data semantics belong to a route or model reached
  through `metab`, with a golden.
  Interaction state machines run browserlessly against the production JavaScript, with a
  session and golden. Only paint stays browser-only, and each exemption names its
  behavior, why a browserless form would be dishonest, and its evidence.
- **Measurement:** measure in headless Chrome through `tests/dom/chrome-session.mjs`,
  not in the app’s built-in browser pane.
  Each pull request includes before and after screenshots, and the large-list features
  include first paint and open times measured against the current behavior.
- **Red, then green:** every new test fails on `main` before its fix.
- **CI:** each pull request runs the full gate.
  Local runs are focused tests plus `make -o install lint-check`.
- **Review:** each pull request gets a senior review (review A, round 1) before it
  merges, with follow-up rounds kept proportionate.

## Rollout Plan

The pull requests ship as drafts in one native stack and merge in order at the owner’s
word. Each bead closes when its pull request merges, with the merge commit in its close
reason. This plan moves to `docs/project/specs/done/` when pull request 6 merges.

## Open Questions

- **Stack grouping default:** should grouping by stack be on by default?
  This plan turns it on when the repository has native stack metadata.
  The choice persists either way.
- **Shared membership:** should a pull request in two stacks appear under each, rather
  than once under the first?
- **Open folders in the Diff summary:** should an open folder also show its line counts?
  This plan leaves that to the implementer, kept consistent with the Files tab’s folder
  tallies.

## References

- **Beads:** epic `mb-eevh`; `mb-s6vu`, `mb-1wfn`, `mb-sogv`, `mb-m5dd`, `mb-epw2`,
  `mb-cm61`, `mb-g3ao`.
- **Earlier pull requests from the same round:**
  - Merged: #433 (`mb-i1wy`), #436 (`mb-jeb5`), #439 (`mb-yfxc`), #435 (`mb-42wk`).
  - In flight: #437 (`mb-a9be`), #438 (`mb-k838`).
  - Deferred: `mb-cz9v`, `mb-o11s`.
- **Project docs:**
  - [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
  - [Design system](../../../design-system.md)
  - [Development](../../../development.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
