# Feature: The Recent Tab: Updates, Events, and Working-Tree Changes

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing here is built.
The owner took every decision under [Key Decisions](#key-decisions), RT-1 to RT-7, on
2026-11-18, with the parent plan’s Decisions 1 to 23. A companion to
[Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), the
parent plan below, whose Decision 19 this plan answers and whose mixed list it designs;
[What This Plan Takes Over](#what-this-plan-takes-over) lists the parts, and
[Settled](#settled) says which of the parent’s decisions this plan rests on.
Written against `main` at `21dc39da7`. Clarifications dated 2026-11-19, from an
independent review, are marked at the decisions they touch.

## Overview

Metabrowser gains a fourth main tab, **Recent**, beside Files, Pulls, and Commits.
It answers one question about the served root: what has been happening here?

The answer has three levels, by what the root is:

- **The folder level,** for a plain folder: the files that changed.
- **The Git level,** for a Git repository: also commits, moved refs, and uncommitted
  changes.
- **The GitHub level,** for a GitHub repository: also pull requests: each one opened,
  closed, or merged, and the pushes, comments, and reviews on it.

Each row is one of two things.
An **update** is a group of changes to one subject within a stretch of time: fourteen
files edited in the working tree over half an hour, or three pushes and two comments on
one pull request. An **event** is one notable change, always in a row of its own: a
commit, or a pull request opened or merged.
Selecting a row shows its diff in the pane, through the diff plugin that draws a commit
today. Uncommitted changes become an object, **working-tree changes**, with an identity,
change totals, and a diff.

## Settled

The owner decided these on 2026-11-18, and this plan does not reopen them:

- **Recent is a main navigation tab,** which answers the parent plan’s
  [Decision 19](plan-2026-11-14-object-data-model-and-views.md#decision-19-where-recent-changes-lives)
  as its option C. Option B’s address survives as `/recent`.
- **It is one surface with three levels,** keyed on what the served root is.
- **The parent plan’s forms apply:** SoftSchema contracts, `pull-request` as that type’s
  one spelling, and UTC strings at second precision.
- **Mixed lists are composed on the server,** the parent plan’s
  [Decision 18](plan-2026-11-14-object-data-model-and-views.md#decision-18-composing-a-mixed-list)
  A.

## What This Plan Takes Over

The parent plan keeps the general rules, and this plan owns what is particular to the
Recent tab.

| In the parent plan | Here |
| --- | --- |
| Its Overview’s third motivating surface | The Recent tab. A page of cards survives as `/recent`, the tab’s list address, in R4 |
| [Mixed Lists](plan-2026-11-14-object-data-model-and-views.md#mixed-lists): a collection may hold several types, in one total order, paged by a cursor | The sources, what each can answer today, and their coverage ([Levels and Sources](#levels-and-sources)); how changes form rows ([Clumping](#clumping)) |
| Decision 18, composing a mixed list on the server | Which sources the first version covers, and each one’s cost |
| Decision 19, decided as C | The tab’s design. Option A is dropped, and folder scope is an [open question](#open-questions) |
| Phase 2, the core types and the folder page | The Recent phases, [R1 to R4](#implementation-plan): the sources, the routes, `[[collection_source]]`, and the page. `R` is the tab’s letter, so no folder view takes it |
| Phase 2’s cards, and the comment types of its Extension Path | Not forced by this surface: cards serve the `/recent` page in R4, and an update counts comments without listing them |

The rest of the parent plan is used as it stands.

## Background

Paths below are under `src/metabrowser/` unless they start with `docs/` or `tests/`;
`github/` abbreviates `builtin_plugins/github/`, and `static/` is the browser shell.

Three things are named Recent:

- **The Files tab’s Recent view.** Setting **Modified within** turns the tree into “the
  Recent view” (`docs/browsing-files.md:80`), read from `/api/recent` and drawn by
  `renderRecentList` (`static/app.js:5474`). It was a tab until the
  [nav filter plan](../done/plan-2026-08-09-nav-filter-controls.md) folded it into
  Files, and three documents still call it “the Recent tab”
  (`docs/project/architecture/arch-recent-targets.md:18`,
  `docs/project/architecture/arch-open-modes.md:209`, `docs/browsing-history.md:125`).
- **Recent targets,** the roots a reader opened, kept by `metab --recent` for File >
  Open Recent ([Recent Targets](../../architecture/arch-recent-targets.md)).
- **This tab.** [RT-6](#rt-6-the-name) settles the collision.

Status and working-tree diffs are not built.
[Git Status and Working-Tree Diffs](plan-2026-08-26-git-status-and-working-tree-diffs.md),
the status plan below, designs `GET /api/git/status`, a status generation, one-file
comparisons, and a `git.status-change` event, and no phase has started.
File Diff Format already has a `worktree` snapshot (`diff/format.py:69`).

## Design

### Levels and Sources

The tab reads one collection, `recent`, which the server composes from registered
**sources**. A source answers its changes in time order, and says whether it applies to
the served root and to the view the server shows.
A **level** is the set of sources that apply, so each level is the one before plus
sources.

| Source | Level | Plain folder | Repository folder, working tree | Repository folder, a revision | Mirror |
| --- | --- | --- | --- | --- | --- |
| `files` | Folder | Yes | Yes; narrowed to uncommitted paths in R2 ([RT-4](#rt-4-file-changes-in-a-repository-folder)) | No: a revision has no modification times | No |
| `working-tree` | Git | No | Yes | No: the view is a revision | No: a mirror has no working tree |
| `commits` | Git | No | Yes | Yes | Yes |
| `refs` | Git | No | Yes, from the reflog | Yes | Only moves this server’s refreshes made, once recorded |
| `pull-requests` | GitHub | No | Where `origin` is on github.com | The same | Where the origin is on github.com |

- **The level is decided where the tabs are.** The Git level applies where the shell
  draws Commits and the GitHub level where it draws Pulls (`server.py:1836`, `:1830`).
- **The tab is about the root, not the view.** The `commits` source walks the history’s
  `all` scope, every branch and tag (`resolve_history_scope`, `git/history.py:317`). The
  default scope of a revision is its own ancestors alone (`git/history.py:303`).
- **Core registers its four sources in Python, and the GitHub plugin its own in its
  manifest.** Core’s are declared in `objects/registry.py`, beside its types and
  collections, and not through a manifest block.
  A plugin’s source joins through the `[[collection_source]]` block that the plugin
  authoring plan specifies
  ([Manifest Blocks](plan-2026-11-18-plugin-authoring-objects-views.md#manifest-blocks)).
- **Coverage is said.** The answer names every registered source with a state: `ready`,
  `pending`, `stale`, `failed`, or `unsupported` for one that applies to the root and
  not to the view, and with `covers_since`, the time before which it lists nothing.
  Where a source ends, the list goes on with the others, and the tab draws one line
  there: “File changes before 09:14 are not listed.”
  An empty tab names the sources it asked.

No source answers a time-ordered cursor today.
Each has a first read that needs little, and a cost to measure before it pages.
Two costs are recorded: the browser’s for a full `/api/recent` answer
(`settings.py:197`) and a first log page’s (`git/ref_state.py:5`).

| Source | Reads today | Needs |
| --- | --- | --- |
| `files` | The newest files in a window, capped, with no cursor (`server.py:3347`, `inventory_engine/contract.py:1172`): current modification times, not a log of writes. The Python provider filters and sorts the whole index for each query (`inventory_engine/providers/python_inventory.py:2718-2747`) | To page, a cursor below a time, from every inventory provider. For edit history, the recorder of [R4](#r4-later-each-alone) |
| `commits` | A log in `--date-order`, which follows topology, with each commit’s time (`git/history.py:641`, `git/log.py:49`) | First, the `all` scope’s first page, ordered by commit time. To page, a bounded walk before a time |
| `working-tree` | Nothing | `GET /api/git/status`, measured by the status plan’s Phase 0. It never pages |
| `refs` | Nothing: no reflog is read, and a mirror records when it last fetched, not what moved (`cache/records.py:357`) | A reflog read; a record of a mirror’s fetches |
| `pull-requests` | Catalog rows with `created_at`, `updated_at`, `closed_at`, `merged_at`, and `head_oid`, indexed by `(state, number)` (`github/pull_list.py:100`, `github/pull_catalog.py:134`); a timeline of commits, comments, and reviews, one pull request at a time (`github/pull_timeline.py:47`) | First, the newest rows by `updated_at`: an event belongs to a row updated at or after it, so they hold every event above a bound. To page, an index on `updated_at` and a table of events |

### Updates and Events

A source answers **changes**, each `{subject, at, kind}`, and declares each kind it
answers as **clumping** or **standalone**: a core source in Python, and a plugin’s in
the `kinds` table of its `[[collection_source]]` block.

| Subject | Clumping kinds, which form updates | Standalone kinds, which are events |
| --- | --- | --- |
| A folder, in a plain folder | A file modified | None |
| Working-tree changes | An uncommitted path modified | None |
| A commit | None | `commit` |
| A branch or tag | None | `ref-moved` |
| A pull request | A commit pushed, a comment, a review that only comments | `opened`, `closed`, `merged`; `approved` and `changes-requested` where a record is cached |

What `main` holds bounds this table.
Opened, closed, and merged come from a catalog row’s own times.
Pushes, comments, and reviews come only from a pull request whose record and timeline
are cached; for any other the source knows `updated_at` alone, and answers an update
with no counts. Reopened and ready-for-review need timeline items the query does not
request.

### Clumping

Clumping decides which rows exist, so it happens on the server, where
[AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity) puts membership and
order. The browser only groups an update’s members by folder, as it clusters
`/api/recent` today (`recent.py:5`). The rule is one pure function over changes, with no
clock as an input:

1. A standalone change is an event.
2. Clumping changes are grouped by subject.
   Two consecutive changes of a subject share an update when they are at most the
   source’s **gap** apart and fall in the same **span**, a fixed interval aligned to UTC
   (`UPDATE_SPAN_S`).
3. An update’s `since` and `until` are its oldest and newest change.
   Its `id` is its subject and `since`, and its `updated_at` is `until`.
4. Rows order by `(updated_at, type, id)`, descending, the parent plan’s total order.

Three properties follow, and each is a test:

- **Local.** An update is fixed by its subject’s changes inside one span.
  The composer reads to the end of the span a page stops in, and a cursor resumes at the
  top of its span and drops what it already answered, so paging holds no state.
- **Append-only.** A new change joins its subject’s newest update or starts one, and a
  growing update keeps its `since`, so its `id` holds.
- **Capped.** No update is longer than a span, and work crossing a span’s boundary makes
  two rows.

One limit is said in the tab: a file update lists the files *last* modified in its span.
A file written twice appears once, at its later time, and leaves the earlier update.
The [edit-history recorder](#r4-later-each-alone) lifts the limit for the writes it saw,
and R1 ships with the limit.

**Live.** The server watches what the sources read, coalesces, and sends one
`recent.change` event with the collection’s `generation` on the page’s stream.
A shown tab then asks for its first page again, and a hidden one waits until shown.
The newest update of each subject is marked `open`, and an `open` row already drawn is
patched in place: its counts, its time, and its change line.
Everything else is offered, as “Show 3 new”, the way late rows are in
[The Pulls Tab](../../../design-system.md#the-pulls-tab), so rows already drawn never
move without input.

### Working-Tree Changes

- **Type.** `working-tree-changes`: what differs between `HEAD` and a repository
  folder’s working tree, staged, unstaged, and untracked together, one entry for each
  path.
- **Identity.** One for each served root:
  `{type: working-tree-changes, id: working-tree}`. It is never minted again.
  Its `head`, Git’s `HEAD` commit and ref, and its `generation`, the status plan’s
  digest over status facts, change as a pull request’s head does.
  A digest has no order, so a reader compares two generations for equality alone.
  Were either its key, a link to it would end at every commit or save.
  What is minted over time is its updates, by the clumping rule.
- **Summary.** `head{ref, sha}`, `generation`, `clean`, `truncated`, and
  `counts{paths, staged, unstaged, untracked, conflicts}`. `updated_at` is the newest
  modification among its paths, and null when clean.
- **Change totals.** The `changes` facet is the shared change-totals sub-object
  (`ChangeSums`, `github/pull_change_sums.py:38`), keyed by `head.sha` and `generation`.
  Status letters come from the status records; a line count may be unknown, which
  `changeLine` draws as “?” (`static/formatters.js:316`).
- **Diff.** A `diff/comparison` document from the `HEAD` commit, or `empty` on an unborn
  branch, to a `worktree` snapshot.
  The status plan’s `GitWorkingTreeDiffSource` builds one entry’s comparison; this plan
  needs one manifest over every path, with hunks deferred, which is new work for that
  plan’s measurement gate.
  The status plan records it under
  [Requirements From the Recent Tab Plan](plan-2026-08-26-git-status-and-working-tree-diffs.md#requirements-from-the-recent-tab-plan).
- **Address.** `/status`, and `/status/<path>` for one file in it
  ([RT-3](#rt-3-the-working-trees-address)), which the status plan records in the same
  section; `?since=&until=` narrows it to one update.
- **Members and freshness.** Its entries are `changed-file` references that name it as
  their parent. A working-tree update holds the entries whose modification time falls in
  its span; a deleted path has no time and takes its parent folder’s. The status plan’s
  `git.status-change` and the inventory’s events feed `recent.change`.
- **In a plain folder** there is no such object.
  Its updates are on the folder and have no diff, since nothing records a base: the row
  opens to its files, and each opens the file.

### The Tab

**Order and key.** Files, Recent, Pulls, Commits: the two tabs every root has come
first, so the tabs that come and go never shift them.
The tab joins `MAIN_TABS` (`static/main-tabs.js:7`), the server draws its button
(`server.py:2487`), and its panel registers as Commits’ does (`registerNavPanel`,
`static/main-tabs.js:210`). Its letter is `R`, which no shell key or view holds
(`keymap.py:66`, `tests/test_keymap.py:115`); Command-R stays the browser’s.

**Rows** are `nav-row`s on the parent plan’s list host, under headings for the reader’s
local day. Selecting one opens its `href`, which is always its subject’s page:

| Row | Says | Change line, its one child | Opens |
| --- | --- | --- | --- |
| Update on the working tree | “Working tree”, “14 files changed”, the age | Statuses and line totals; opens to the files | `/status?since=…&until=…`: the working-tree comparison, narrowed to the update’s paths |
| Update on a folder | The deepest folder holding every member, the file count, the age | Opens to the files | `/view/<folder>`: the folder page |
| Update on a pull request | Its title and number, “3 commits, 2 comments”, the age | The pushed range’s totals, where known | `/pull/<n>/files`; the pushed range alone once `/compare/` exists |
| Event | The subject’s title, what happened, the number or short ID, the actor, the age | None in R1 | `/commit/<id>`, a `diff/comparison` document (`builtin_plugins/diff/sidekick.py:302`), or `/pull/<n>` |

**Reveal.** Today an address belongs to one tab (`tabAtAddress`,
`static/main-tabs.js:36`), so a commit opened from Recent would bring Commits forward.
The rule gains a case: a row opened from the tab in front keeps that tab in front, and a
load at the address reveals the item in its own tab.
`/status` belongs to Commits, where the status plan’s Changes section lists the same
paths: a load at `/status` reveals it in Commits, and a working-tree update opened from
Recent keeps Recent in front, by this case.
[Navigation Reveals the Item](../../../design-system.md#navigation-reveals-the-item)
changes with it.

**Keys** are those of
[Navigational Row Collections](../../../design-system.md#navigational-row-collections),
as in Pulls: Right goes to the change line, and Enter or Space there opens the files.

### Contracts

Three contracts join the parent plan’s object family.
Each is the shared header plus:

| Contract | Summary | Facets |
| --- | --- | --- |
| `metabrowser.objects:Update/v1` | `subject`, a reference; `since`; `until`; `open`; `counts`; `members`, a bounded list of references, newest first; `members_truncated` | `changes`, keyed by the comparison it totals |
| `metabrowser.objects:Event/v1` | `kind`; `subject`; `detail`, small and by kind, such as a moved ref’s `from` and `to` | `changes` |
| `metabrowser.objects:WorkingTreeChanges/v1` | As [above](#working-tree-changes) | `changes` |

The implementation map’s C2 registers `WorkingTreeChanges` with the other core types,
and R1, which follows C2, registers `Update` and `Event` in the same registry.

An event’s `id` is its subject, kind, and time.
Its `kind` is a token its source declares, so core’s contract names no GitHub concept.
A first page in a GitHub checkout, as `--api --format yaml` prints an envelope, with
synthetic values:

```yaml
generation: "…"                     # opaque: compared for equality
complete: false
truncated: false
next_after: "…"                       # opaque: the last row's position
sources:
  - {id: files, state: ready, covers_since: "2026-11-17T08:02:40Z"}
  - {id: working-tree, state: ready}
  - {id: commits, state: ready}
  - {id: refs, state: ready}
  - {id: pull-requests, state: stale}
rows:
  - type: update                      # local edits, still open
    id: working-tree-changes/working-tree@2026-11-18T17:05:10Z
    href: /status?since=2026-11-18T17:05:10Z&until=2026-11-18T17:31:42Z
    title: Working tree
    updated_at: "2026-11-18T17:31:42Z"
    subject: {type: working-tree-changes, id: working-tree}
    since: "2026-11-18T17:05:10Z"
    until: "2026-11-18T17:31:42Z"
    open: true
    counts: {files: 14}
    members:
      - type: changed-file
        id: src/app/tabs.js
        parent: {type: working-tree-changes, id: working-tree}
    members_truncated: true
    changes:                          # facet
      head: 0123456789abcdef0123456789abcdef01234567
      generation: "sha256:…"
      files: 14
      additions: 412
      deletions: 96
      statuses: [[added, 3], [modified, 11]]
  - type: update                      # pushes and comments on one pull request
    id: pull-request/41@2026-11-18T15:02:11Z
    href: /pull/41/files
    title: Add the Recent tab
    updated_at: "2026-11-18T16:40:03Z"
    subject: {type: pull-request, id: "41"}
    since: "2026-11-18T15:02:11Z"
    until: "2026-11-18T16:40:03Z"
    open: true
    counts: {commits: 3, comments: 2}
  - type: event                       # always its own row
    id: pull-request/42/opened@2026-11-18T14:55:30Z
    href: /pull/42
    title: Fix a typo in the guide
    updated_at: "2026-11-18T14:55:30Z"
    actor: {name: example-author, login: example-author}
    kind: opened
    subject: {type: pull-request, id: "42"}
  - type: event                       # a commit
    id: commit/89abcdef0123456789abcdef0123456789abcdef/commit@2026-11-18T14:20:05Z
    href: /commit/89abcdef0123456789abcdef0123456789abcdef
    title: Rename the files route
    updated_at: "2026-11-18T14:20:05Z"
    kind: commit
    subject: {type: commit, id: 89abcdef0123456789abcdef0123456789abcdef}
```

### Routes, the CLI, and the View Model

- **Routes.** `GET /api/recent` answers the collection in the parent plan’s collection
  convention, with `after`, `limit`, and `sources`; [RT-6](#rt-6-the-name) gives the
  name. `GET /api/recent/item?type=&id=` answers one update or event, composed again from
  its subject’s span; one that no longer exists is `not_found`, never a neighbor.
  `GET /api/git/working-tree` answers the working-tree changes object.
  These are where a reference to each type leads.
- **The CLI.** `--api` reaches them, and no mode is added: `--recent` is the recent
  targets’ (`cli/main.py:720`).
- **View state.** In the view model plan’s
  [view state](plan-2026-11-18-view-model-and-view-state.md#the-view-state), `nav.tab`
  is `recent`, `nav.current` is the row’s reference, an `update` or an `event`, and
  `nav.list` names `{name: recent, params: {}}`. `object` stays what the address
  selects: the commit or the pull request.
- **Intents.** `present` with an `update` or an `event` opens its `href` with Recent in
  front and that row current.
  `present` with the subject itself is unchanged, and reveals it in its own tab.

### Parity and Testing

| Row | Tier | Evidence |
| --- | --- | --- |
| `/api/recent`, `/api/recent/item`, `/api/git/working-tree` | Route, covered | `--api` goldens over fixture roots with pinned times: a plain folder, a repository, and a GitHub cache home built as `tests/test_github_drawn_from_disk.py` builds one. `/api/git/working-tree`’s row and golden arrive first, with the implementation map’s T1.3, and `--show /status`’s with its T1.5 |
| `recent.membership`, `recent.paging`, `recent.coverage` | Data, owned by `/api/recent` | Gap and span splits, standalone kinds, order, and ties; pages cut at every row equal the unpaged answer; each source state, on a revision, on a mirror, and when empty |
| `recent.panel` | Interaction | `tests/dom/recent-panel-session.js` runs the production `describe` functions, the patch of an `open` row, the offer, and the reveal case |
| `recent.row-paint` | Paint-exempt | In headless Chrome: a row’s height holds when its change line arrives, and four tabs fit the default pane |

The clumping function gets table tests and the three properties as tests, and each
contract a corpus. The test that `R` is free (`tests/test_keymap.py:115`) asserts the
opposite.

### Performance

Nothing here is measured.
Each bound is set by a measurement recorded beside its constant: `UPDATE_SPAN_S`, each
source’s gap, the member cap, the page size, and the debounce of `recent.change`.

- **One composition at a time for each root,** the newest request winning.
- **The page’s stream keeps its depth.** A page’s connection is filtered to two levels
  (`events_route.py:661`), and the bus behind it carries every change, so the composer
  watches the bus and the page receives one small event.
  A pinned revision has no stream today (`events_route.py:773`), so a mirror’s tab
  refreshes when its source does.
- **A first-page read is not free.** The folder level is a pass over the index, the Git
  level adds a status read, and the GitHub level a catalog read that scans until
  `updated_at` has an index.
  A large repository sets the bounds: a storm of build output, a branch switch that
  touches every file, and a catalog of tens of thousands of pull requests.
- **Loading.** The panel loads on first show, and the list host windows its rows.
  Its first page is prefetched in idle time only if a measurement shows the index pass
  does not delay the tree.

## Key Decisions

Each gives the phase that needs it, the options it weighed, and the decision.
The owner took all seven on 2026-11-18.

### RT-1: The Item Model

**Needed for:** R1.

- **A. Two derived types, `update` and `event`,** each naming a subject by reference.
  One row vocabulary for every level, and “opened” and “pushed to” are separate rows of
  one pull request.
- **B. The subjects themselves in a mixed list,** ordered by `updated_at`, as the parent
  plan first drew it. A pull request has one row, which cannot say what happened, and
  file changes have no subject to gather under.

**Decided 2026-11-18: A.**

### RT-2: The Clumping Rule

**Needed for:** R1.

- **A. A gap, within a span aligned to UTC.** Local, append-only, and stateless to page.
  It splits work that crosses a span’s boundary.
- **B. Fixed buckets alone.** It merges unrelated bursts and splits one at every
  boundary.
- **C. A gap, with a cap measured from the update’s start.** The most natural blocks.
  Finding a start means walking a chain of unbounded length.
- **D. A gap, with a cap measured from the newest change.** Every boundary in a chain
  moves when the chain grows, and rows and identifiers with it.

**Decided 2026-11-18: A,** with the span and the gaps chosen from recorded sessions.

### RT-3: The Working Tree’s Address

**Needed for:** the working-tree page, before R2.

- **A. One space by path.** `/status` is the whole comparison and `/status/<path>` one
  file in it, the grammar’s container and inner path, in the `/view/` codec, which
  spells any filename.
  The status plan’s staged and unstaged rows become `?scope=` on the same path.
- **B. The status plan’s `/status/<scope>/<entry-id>`,** with `/status` added as its
  root. Two rows of one file stay apart by construction, and a member’s address is a
  digest no reader can write.
- **C. A second space, `/changes`.** Two addresses for one file’s uncommitted diff.

**Decided 2026-11-18: A,** which changes the status plan, as its
[Requirements From the Recent Tab Plan](plan-2026-08-26-git-status-and-working-tree-diffs.md#requirements-from-the-recent-tab-plan)
records; B if its gate finds a path the codec cannot spell.

**Clarified 2026-11-19:** the Commits tab owns `/status` and `/status/<path>`, since the
status plan’s Changes section lives there.
A load at either reveals it in Commits, and a row opened from Recent keeps Recent in
front ([The Tab](#the-tab)).

### RT-4: File Changes in a Repository Folder

**Needed for:** R1 and R2.

- **A. Every modified file that is not ignored.** All that R1 can do.
  A pull or a branch switch fills the tab with files a commit already explains.
- **B. Only the paths Git status reports,** with a status letter and a diff.
  It needs the status plan.

**Decided 2026-11-18: A in R1,** labelled “files changed” and never “uncommitted”, **and
B from R2.**

### RT-5: What Stands Alone

**Needed for:** R1 for commits; R3 for reviews.

- **A. Every commit in the `all` scope is an event.** A review with a verdict is an
  event, and one that only comments clumps.
- **B. Commits that arrive by one ref move clump under it.** Fewer rows after a pull.
  It needs the `refs` source, and folds away commits the owner asked to see.

**Decided 2026-11-18: A,** with B weighed again once a `refs` source exists.

### RT-6: The Name

**Needed for:** R1.

- **A. Keep the Files filter and retire its name.** The control stays **Modified
  within**, and documents stop calling its result Recent.
  `/api/recent` becomes `/api/recent-files`, changed with its readers in one commit, and
  the tab takes `recent`, `/api/recent`, and `/recent`. Recent targets keep their name:
  they are roots, outside any served root.
- **B. Keep every name.** The tab reads `/api/recent-changes`, and `/api/recent` is not
  the Recent tab’s route.
- **C. Fold the Files filter into the tab.** It loses the filter’s composition with
  type, size, and grouping, which is why the earlier tab was folded into Files.

**Decided 2026-11-18: A.**

### RT-7: The First Slice

**Needed for:** R1, before anything else.

- **A. The recent slice: the folder level and commits, on the list host,** after the
  store and the list host of the parent plan’s object slice.
  The tab is the host’s first navigation panel and its first mixed list.
- **B. A panel built by hand, before the list host.** Sooner, and one more
  implementation of row mechanics for the parent plan’s Phase 3 to replace.
- **C. Wait for the status plan,** and ship the Git level whole.

**Decided 2026-11-18: A.**

**Clarified 2026-11-19:** R1 also follows the object contract registry, the
implementation map’s C2. It adds two contracts with a corpus, and the registry, the
compiled schemas, and the corpus checks they need arrive there.
The tab’s rows use the navigation-column key contract, which the list host provides
beside the pane’s.

## Implementation Plan

The [implementation map](plan-2026-11-18-object-model-implementation-map.md) orders
these among the parent plan’s stacks.

### R1: The Recent Slice

After the store and the list host of the parent plan’s Phase 1, and after the contract
registry of its Phase 2, the implementation map’s C2.

- [ ] Add `updates/`: the source registry, the clumping function, the composer, and the
  routes; the `files` and `commits` sources, declared in `objects/registry.py`; the
  `Update` and `Event` contracts with their corpus, registered in the object contract
  registry.
- [ ] Add the tab: its button, `R`, and `static/recent-panel.js`, loaded on demand, with
  `nav-row` views for both types on the list host’s navigation-column key contract, day
  headings, and the change line that opens to an update’s files.
- [ ] Add `recent.change`, the live rule, the reveal case, and `/recent` with a
  placeholder page.
- [ ] Make RT-6’s renames, and change the documents that say “the Recent tab”, the
  keyboard table, the design system’s [Main Tabs](../../../design-system.md#main-tabs),
  the map, and the parity rows.
- [ ] Measure the first-page read on a large root, and four tabs in the default pane,
  before setting a bound.

### R2: Working-Tree Changes

The object, its route, its manifest over every path, and its page are built first, as
the implementation map’s Tier 1, to this plan’s definition.

- [ ] Add the `working-tree` source, the narrowing of `/status` to an update, and RT-4
  B. Where Tier 1 has landed, this joins R1.

### R3: The GitHub Level

- [ ] Add `[[collection_source]]`, with its `kinds` table, and the `pull-requests`
  source: events from catalog rows, with an index on `updated_at`, which is a catalog
  schema change; updates from cached records and timelines.
- [ ] Count the Recent tab as a shown list of `pulls`, so the catalog refreshes while
  Recent is in front (the parent plan’s Decision 14).

### R4: Later, Each Alone

- [ ] The `refs` source.
- [ ] `/recent` as a page of cards, the first real use of the `card` shape.
  Its frame is built here and not before, with the commit’s and the pull request’s cards
  (the parent plan’s
  [Decision 11](plan-2026-11-14-object-data-model-and-views.md#decision-11-the-set-of-shapes)).
- [ ] Cursors that reach past each source’s first read.
- [ ] The tab’s `nav.list` facet.
- [ ] `/compare/` for a pushed range.
- [ ] An edit-history recorder, so that a file update is real edit history and not a
  group by last modification time.
  R1 does not wait for it.
  - **What it records.** It subscribes to the bus the composer watches and logs each
    file change as it happens: the path, the time, and the kind of change, never
    content. The `files` source answers from the log wherever the log covers a span, so a
    file written twice appears in both updates, and falls back to modification times
    elsewhere.
  - **What it cannot know.** It sees only what a running server saw.
    A change made while no server ran, or before the log begins, is listed by its
    modification time, and the source’s coverage says where the log starts.
  - **Measured and bounded.** The log is new persisted state.
    Its write rate under a build’s storm of output, its size, and its retention are
    measured before it ships, and each bound is a constant with its measurement beside
    it.
  - **Where it is kept.** In durable storage the user owns, readable by the owner alone,
    since it holds private file names, and never in a temporary directory, which
    [Durable Storage](../../../../AGENTS.md#durable-storage) rules out for anything a
    later session depends on.
    The log cannot be computed again, so by the reasoning that put recent targets in the
    configuration directory
    ([Recent Targets](../../architecture/arch-recent-targets.md)) it does not belong in
    the cache, which may be deleted at any time; its measured size decides whether it
    sits beside them or in a directory of its own.

## Open Questions

- **What does each source cost, and how long are the span and the gaps?** None is
  measured, and one gap may not suit both file writes and pull request activity.
- **Is a parent folder’s time right for a deleted path?** It moves again when a sibling
  is added.
- **Where do ref moves come from?** Does a reflog read fit the read-only rule and the
  process policy, and what should a mirror record of its fetches?
- **Scoping to a folder.** A `path` parameter would give a folder what Decision 19 A
  described.
- **Ignored files** are left out, as `/api/recent` drops them first.
  Should the tab get Show ignored?
- **A squash merge** yields a merged event and a commit event for one act.

## References

- [Object Data Model and Views](plan-2026-11-14-object-data-model-and-views.md), the
  parent plan;
  [View Model and View State](plan-2026-11-18-view-model-and-view-state.md);
  [Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md);
  the [implementation map](plan-2026-11-18-object-model-implementation-map.md);
  [Git Status and Working-Tree Diffs](plan-2026-08-26-git-status-and-working-tree-diffs.md),
  and the [nav filter plan](../done/plan-2026-08-09-nav-filter-controls.md)
- [Open Modes](../../architecture/arch-open-modes.md),
  [Recent Targets](../../architecture/arch-recent-targets.md),
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md),
  [Git](../../architecture/arch-git.md),
  [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md), and the
  [Parity Registry](../../architecture/arch-parity-registry.md)
- [Design System](../../../design-system.md): Main Tabs, The Pulls Tab, Navigational Row
  Collections, Navigation Reveals the Item

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
