# Feature: Object Data Model and Views

**Date:** 2026-11-14

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Decided, and nothing here is built.
The owner took every decision here, 1 to 23, on 2026-11-18, and
[Key Decisions](#key-decisions) gives each choice.
Revised 2026-11-18 against `main` at `a1100bca6`, and against the pull requests under
[Work in Flight](#work-in-flight), of which #550, #552, and #534 have since merged.
Some of what the plan proposes now exists on `main`: a shared page header, a view header
for files and folders, a drawing of an author, and a pull request’s change totals served
and drawn as one facet.
The plan builds on those pieces instead of designing them again.

Five companion plans carry parts of the design, and this plan is the parent of each:

- [View Model and View State](plan-2026-11-18-view-model-and-view-state.md): what each
  viewer shows, and how an agent reads and changes it.
  It holds [the view model](#the-view-model), Phase 4, and Decisions VM-1 to VM-10.
- [The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md): the mixed list of
  what changed, which answers Decision 19 and designs on Decision 18.
- [Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md):
  the manifest, JavaScript, and Python a plugin writes.
- [Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md): the
  commands an agent runs.
- The [implementation map](plan-2026-11-18-object-model-implementation-map.md): the
  phases as stacks of pull requests.

## Overview

Metabrowser draws four things over and over: files, folders, commits, and pull requests.
Each appears as a narrow row in the navigation panel and as a page in the main pane, and
today each is modeled again for every place it appears.

This plan gives each of them one model, an **object** with a
[SoftSchema](https://github.com/jlevy/softschema) contract, and lets that one model feed
several **views**: a narrow navigation row, a wide row, a card, and the detail page.
A list of objects is a **collection**, drawn by one shared list component in whichever
view shape a surface needs.

Three surfaces motivate it.
None needs data the product does not already hold; each needs the same data drawn a
second way.

- **A pull requests page** at `/pulls`: the pull requests the Pulls tab lists, as wide
  rows that show more of each one, in the manner of GitHub’s pull requests page.
- **A folder page** that breaks a folder down into its subfolders and files, as wide
  rows.
- **A Recent tab:** a main tab of what changed in the served root, commits, pull
  requests, and changed files, mixed and ordered by time.
  [The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md) designs it.

The objects say what each thing is.
A second model, the **view model**, says what each window shows, by reference to these
objects, so that an agent can read what the reader is looking at and ask a viewer to
show something.
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md)
designs it, on the definitions this plan gives.

## Goals

- One model for each top-level object type (file, folder, commit, pull request), with a
  stated identity, a SoftSchema contract, and one definition of every field.
- Named view shapes, so the navigation row and the wide row of a pull request are two
  drawings of one object and not two templates over two models.
- One browser data model: views read objects and collections from one store interface,
  whichever route or event stream supplied them.
- One list component for long lists of objects, including lists that mix types, with the
  windowing, keyboard, and loading rules the design system already sets.
- A way for a plugin to declare an object type, its contract, and its views, inside the
  `PLUGIN_SDK_VERSION` gate.
- Every object and collection reachable through `metab` and pinned by a golden, as
  [AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity) requires.
- An incremental path: the object model’s first step, the **object slice**, ships one
  new page, changes what one existing surface reads, behind a measurement, and redraws
  none.
- One vocabulary for the object model and the view model: a reference, a collection
  reference, a shape, a summary and facets, and a `generation`, each defined once, here.

## Non-Goals

- Redrawing the Files tree, the Commits graph, the Pulls panel, or the pull-request page
  as a precondition. They adopt the model surface by surface, each behind its own
  measurement ([Phase 3](#phase-3-converge-the-existing-surfaces)).
- Changing File Diff Format, File Rollup Format, or the repository cache’s record
  contracts.
- Modeling file *content*. A file’s page stays the `/api/file` envelope and the views of
  its kind.
- Publishing `/api/*` as a supported external API
  ([Decision 2](#decision-2-standing-of-the-contracts)).
- Building every example.
  The folder page and the Recent tab are designed so the model is proved against them;
  only the pull requests page is in the object slice.
- A plugin navigation panel, router, or address space, which
  [Plugin System](../../architecture/arch-plugin-system.md#registration-surfaces-not-built)
  records as not built.

## Background

Paths below are under `src/metabrowser/` unless they start with `docs/`, `tests/`, or
`devtools/`; `github/` abbreviates `builtin_plugins/github/`, and `static/` is the
browser shell.

### A Selection Has One Model and One View

[Views, Models, and Routes](../../architecture/arch-views-models-routes.md) describes
the architecture as four layers a *selection* travels: address, resource kind, model,
view. It fits one thing shown in the pane.
It has no place for the same thing shown as a row, or for many things shown together:

- **A kind selects renderers; it is not an object type.** `markdown`, `html`, and
  `image` are kinds of file.
  A list has a kind of its own, `pull-request-list`. A commit has none: `/commit/<rev>`
  selects the `comparison` kind, and the commit’s subject, author, and totals are drawn
  by shell code, not a registered view (`static/git-panel.js:449`), in the
  `.page-header` the pull request page also uses
  ([Page Headers](../../../design-system.md#page-headers)).
- **A view is a tab in the pane.** `[[view]]` and `mb.registerView` register page views
  only. Nothing registers how a kind looks as a row.
- **The one list in the pane is a placeholder.** The `pull-request-list` view mounts
  twice: in the Pulls tab with a host context, and in the pane at `/pulls`, where it
  draws “Select a pull request.”
  (`github/index.js:21`, `github/pulls-panel.js:5507`).

### How Each Object Is Modeled Today

No type on the server or in the browser stands for “a file” or “a pull request” across
routes. The closest are `FsEntry` (`fs_record.py:46`), which the inventory holds for
every file and folder, and the GitHub plugin’s Pydantic records.
Each object has several models, one per surface.

**File.**

| Where | Shape | Defined at |
| --- | --- | --- |
| `/api/tree` row | `FileNode`: `name`, `path`, `type`, `size`, `mtime` (seconds), optional `ext`, `logical_ext`, `compressed`, `compression`, `gitignored` | `wire_models.py:58` |
| `/api/events` change | `FsEntry`: `path`, `parent`, `name`, `type`, `ext`, `kind`, `size`, `mtime_ns`, `mtime_hash`, `active`, `views`, `labels` | `fs_record.py:46`, `events.py:317` |
| `/api/recent` row | `name`, `path`, `type`, `size`, `mtime`, `ext`, optional `gitignored` | `recent.py:56` |
| `/api/catalog` row | `{"p": path, "e": logical extension}`; size and time dropped on purpose | `events_route.py:1253` |
| `/api/file` envelope | A dict per content type: `type`, `kind`, `views`, `path`, `ext`, `size`, `mtime_hash`, and a content window; no `name`. Since #550, which merged after `a1100bca6`, it also carries `mtime` in epoch seconds, left out where the time cannot be read (`_mtime_field` in `server.py`) | `server.py:3726` |
| On a pinned revision | `path` as a `GitPath` wire, plus `display`, `mode`, `git_kind`, `symlink`, `gitlink`, `oid`; no time | `git/content_routes.py:245` |
| Quick Search result | `kind: "file"`, `id`, `label`, `description`, `path`, `logicalExtension`, ranking fields | `static/search-controller.js:103` |

**Folder.**

| Where | Shape | Defined at |
| --- | --- | --- |
| `/api/tree` row | `DirNode`: `name`, `path`, `type`, `children`, `total_files`, `total_size`, `mtime`, optional `has_children`, `gitignored`, `empty` | `wire_models.py:87` |
| `/api/events` change | `FsEntry` with `total_files`, `total_size`, `unignored_files`, `unignored_size`, `newest_mtime_ns`, `empty` | `fs_record.py:46` |
| `/api/file` envelope | `type: "folder"`, `kind`, `path`, `name`, `views`, `dir{…totals, mtime, gitignored, state}`, `readme_path` | `server.py:3350` |
| `/api/rollup` node | `RollupDirNode`: totals, `state`, `dominant_ext`, `children`, `rest` | `wire_models.py:228` |
| Browser totals store | `{path, revision, state, totalFiles, totalBytes, unignoredFiles, unignoredBytes}` | `static/directory-totals-store.js:44` |

**Commit.**

| Where | Shape | Defined at |
| --- | --- | --- |
| `/api/git/log` row | `GitCommit`: `id`, `short_id`, `parent_ids`, `author{name, email}`, `authored_at`, `committed_at` (seconds), `subject`, optional `refs` | `git/wire.py:100` |
| `/api/git/commit/<rev>` | `GitCommitDetail`: `commit`, `body`, `stats`, `files`, `files_truncated` | `git/wire.py:263` |
| In a pull request’s timeline | `kind: "commit"`, `oid`, `subject`, `committed_at` (ISO string) | `github/pull_timeline.py:74` |
| In a pull-request record | `commits`, a count | `github/pull_record.py:204` |
| The `/commit/<rev>` page | A `diff/comparison` document in File Diff Format; `--show` reads this and not `/api/git/commit` | `cli/show_cli.py:449` |

**Pull request.**

| Where | Shape | Defined at |
| --- | --- | --- |
| Catalog row, `GET pulls` | `PullListRow`: `number`, `title`, `state`, `draft`, `merged_at`, `author`, `author_avatar_url`, `created_at`, `updated_at`, `closed_at`, `base_ref`, `head_ref`, `head_repository`, `labels`, `head_oid`; the wire adds `merged` | `github/pull_list.py:99`, `github/pull_catalog.py:531` |
| Record, `GET pull` | `PullRequest` inside `PullRecord`: adds `body`, `merged`, `merged_by`, `commits`, `merge_commit_sha`, `mergeable`, `html_url`, labels as `{name, color, description}` where a row has names, and `base` and `head` as `{ref, sha, repository}` | `github/pull_record.py:187`, `:325` |
| Core preview | `CachedCore` on disk and `PullCorePreview` on the wire | `github/pull_core_cache.py:36`, `github/served_pull.py:81` |
| Search row, `GET pulls?q=` | `number`, `title`, and a four-valued `state` | `github/pull_catalog.py:540` |
| Navigation row, in the browser | `PullRow`: camel case (`stateLabel`, `updatedAt`, `meta`), no branches, and the head commit as `head`, which the row does not show but which its change line is read again for when it moves | `github/pulls-panel.js:234`, `:312` |
| Change totals, `GET pull-files-summary?numbers=` | `FilesSummaryWire`: `head`, `base`, `base_ref`, `generation`, nullable `files`, `additions`, and `deletions`, `exact`, and `statuses`; batched up to `MAX_SUMMARY_NUMBERS`, answered from the cache alone | `github/pull_files_summary.py:98`, `:64` |
| A stack’s change totals, `GET stack-change` | `StackChangeEnvelope`: the stack’s combined change, not a sum of its members’ | `github/pull_stack_change.py:109` |
| Page header, in the browser | A second description built from the record | `github/pull-page.js:1174` |

A pull request’s nested parts are modeled the same way, once per use: comments and
reviews as record items (`github/pull_record.py:221`, `:233`, `:246`) and again as
timeline events that carry only a kind and an identifier (`github/pull_timeline.py:81`),
which the page joins to the record’s cards by `kind/id` (`github/pull-page.js:5420`);
check runs (`github/pull_record.py:270`); changed files (`github/pull_list.py:299`); and
stacks (`github/pull_stacks.py:76`).

The change totals are the exception, and the nearest thing to a facet that exists.
One route serves them, keyed by the head and base they describe; one browser memory per
document holds them (`documentRowLines`, `github/row-lines.js:157`); and the Pulls row,
the stack heading, and the pull request page’s brief line all read that memory, so a
page opened from a row asks for nothing (`github/pull-summary-brief.js`).

### Where the Same Fact Is Spelled Differently

| Fact | Spellings |
| --- | --- |
| A file’s modification time | `mtime` in seconds (`wire_models.py:58`, and on the `/api/file` envelope since #550), `mtime_ns` (`fs_record.py:46`), `mtime_hash` (`server.py:3595`), `newest_mtime_ns` for a folder, absent in the catalog and on a pin |
| A time, in general | Epoch seconds in the tree and Git wires (`git/wire.py`, module docstring); UTC strings at second precision in GitHub models (`github/pull_record.py:108`) and with optional milliseconds in cache records (`cache/records.py:58`); nanoseconds in the event stream |
| A pull request’s state | `state` and `draft` and `merged_at` in a row; `state`, `draft`, and `merged` in a record; one four-valued `state` in search; and “state” also names every envelope’s cache state |
| That four-valued state | Derived four times: `displayState` (`github/pull-state.js:43`), the search projection (`github/pull_catalog.py:640`), a record’s summary line (`github/pulls.py:1239`), and `--show` (`cli/show_cli.py:248`); and inverted once, in `withListedState` (`github/pull-state.js:118`) |
| A pull request’s branches | `base_ref`, `head_ref`, `head_repository`, `head_oid` in a row; `base.ref`, `head.sha`, `head.repository` in a record |
| A commit’s identifier | `id`, `oid`, `revision`, `head_revision`, `sha` |
| A change’s totals | `GitCommitStats` with six counts (`git/wire.py:243`); the diff format’s `Totals{files, additions, deletions, exact}` (`diff/format.py:170`); per-file `additions` and `deletions` in `GitFileChange` and `PullFileRow`, whose status words differ; on the server, `ChangeSums{files, additions, deletions, exact, statuses, short}`, which fixes the status words (`github/pull_change_sums.py:38`); in the browser, the `{files, additions, deletions, exact}` that `changeSummary` and `changeLine` draw, where an unknown count draws as “?” (`static/formatters.js:304`, `:393`) |
| What kind of thing | `type` is `file` or `dir` in a tree row and `text`, `folder`, or `image` in an envelope; `kind` is a view classifier in an envelope, a ref’s kind in Git, and a blob or tree on a pin; `--present` prints a `kind` of `folder`, `file`, `repository`, `pull_request`, `commit`, or `tree`, which the macOS app reads (`cli/present.py:126`); and a selection’s `SelectionKind` is `repository`, `tree`, `blob`, `commit`, or `pull_request` (`cache/urls.py:77`) |

### How Each Object Is Drawn Today

Every surface builds its own rows.
There is no shared row or list helper; the design system’s
[Descriptor Contract](../../../design-system.md#descriptor-contract) describes keyboard
commands, not rows. Below the row, three drawings are shared: a page header, an author,
and change totals.

| Surface | Builder | Notes |
| --- | --- | --- |
| Files tree | `renderTreeNodes` (`static/app.js:2538`) and, for live inserts, `_buildRowHtml` (`static/app.js:8210`) | Two builders over two shapes of one entry, which the design system holds together with a test ([Navigation Tree Folders](../../../design-system.md#navigation-tree-folders)) |
| Recent | `renderRecentList` (`static/app.js:5575`) | Reuses `renderTreeNodes` over a clustered tree |
| Quick Search | `appendFileResult` and `appendPullResult` (`static/search-palette.js:436`, `:472`) | An option builder per kind of result, over a `file` or `pull` result union |
| Commit row | `renderRow` (`static/git-panel.js:2183`) | Reads the log row |
| Commit summary | `renderCommitSummary` (`static/git-panel.js:449`) | One component in two projections: the page’s header and, with `compact`, the hover card |
| Pull request row | `describeRow` then `buildRow` (`github/pulls-panel.js:312`, `:3951`) | A pure description, then paint. Three lines: the title first, then the number and author, then the change line, which is the row’s one child and its own focus stop ([The Pulls Tab](../../../design-system.md#the-pulls-tab)) |
| Stack heading | `createStackLines` (`github/stack-lines.js:234`) | A section heading that reads data of its own, the stack’s change line from `stack-change`; a row in a stack sits one slot in, a row in none flush left |
| Pull request header | `describeCore` then `paintHeader` (`github/pull-page.js:1174`, `:4955`) | A second description of the same pull request |
| Page header | `.page-header` on the commit and pull request pages | Lines in one order: title, author, place, age, then the Diff summary ([Page Headers](../../../design-system.md#page-headers)) |
| Author | `metabrowser.actorIdentity(name, {avatar, placeholder})` (`static/plugin-sdk-views.js:1063`) | The commit page, the pull request page, and the Pulls rows draw an author through it |
| Change totals | `changeLine` and `changeSummary` (`static/formatters.js:304`, `:393`) | One drawing on the commit card, the commit totals, the Diff summary, the Pulls rows, the stack headings, and the pull request page’s brief line |
| Folder Overview | A panel stack (`builtin_plugins/folder/overview.js:83`) | Totals, type breakdown, README; no list of children |

Four of these are precedents this plan builds on.
`describeRow` separates a pure description from paint, and a browserless session pins it
(`github.pulls-panel` in the
[Parity Registry](../../architecture/arch-parity-registry.md)). `renderCommitSummary`
draws one component at two sizes, which `test_git_commit_summary_is_one_component` holds
to one renderer. The page header and `actorIdentity` are drawings of the shared header
and of the `actor` sub-object below, already extracted; `changeLine` is the drawing of
the change-totals sub-object.

Long lists are windowed three ways: a fixed-height window for Git history
(`static/git-history-window.js:172`), a variable-height one for pull requests
(`github/pulls-window.js:8`), and a third for a pull request’s changed files
(`github/pull-files-view.js:286`). The Files tree pages by `TREE_PAGE_SIZE`
(`static/app.js:16`) and does not window.

The keyboard rules for these lists are one contract,
[Navigational Row Collections](../../../design-system.md#navigational-row-collections),
implemented four times (`static/tree-keyboard-navigation.js:491`,
`static/git-panel.js:1823`, `static/pulls-nav.js:461`, and the changed-files tree) and
held together by a source-text check,
`test_nav_like_row_sets_share_the_vertical_keyboard_contract`
(`tests/test_design_vocabulary.py:599`). In the Pulls tab, Right moves to a row’s change
line, Space on the row is consumed and does nothing, and Up and Down never expand.

### Browser Stores Today

[Browser Shell](../../architecture/arch-browser-shell.md#stores) lists the shell’s
stores. Each surface also keeps its own:

| Store | Keyed by | Kept fresh by |
| --- | --- | --- |
| `fileStore` (`static/app.js:7830`) | Path, one `FsEntry` each | The event stream, within its depth scope |
| Directory totals (`static/directory-totals-store.js`) | Path | The same events; subscribers per path |
| Folder context (`static/resource-context.js`) | Path, the folder envelope | A refetch on an intersecting change |
| File cache (`static/app.js:6418`) | Path, the `/api/file` envelope | Entity tags |
| Known-file catalog (`static/known-file-catalog.js`) | Path | One bulk read, then catalog deltas |
| Git pages and details (`static/git-panel.js:76`, `:120`) | Page number; revision | A generation that moves with HEAD |
| Pull lists (`github/pulls-panel.js:710`) | Filter name | A content generation, entity tags, and polling |
| Listed states (`github/pull-state.js:60`) | Source, then number | Written as rows arrive |
| Row change lines (`documentRowLines`, `github/row-lines.js:157`) | Number and head | Read again when a row’s head moves; bounded, per document |
| Stack change lines (`documentStackLines`, `github/stack-lines.js`) | Stack | Read again when a member’s head moves |

Four findings matter for the design.

- **The pull list store holds descriptions, not pull requests.** `holdRows` maps each
  wire row through `describeRow` and keeps the result (`github/pulls-panel.js:1587`), so
  the labels, branches, creation time, and close time a wider row would show are
  discarded when the row arrives.
- **The pull list lives inside the panel.** `createPullsController` is created by the
  panel’s mount (`github/pulls-panel.js:707`, `:4852`), reads only while the tab is
  shown (`:921`), and holds at most `DISPLAY_ROWS` rows.
  Nothing outside the panel can read its list.
  The change-line lane is created in the same mount (`:5028`), and asks for no lines
  while the panel is hidden (`:4541-4547`).
- **A row and its page reconcile by hand.** The page reads a different model from the
  row, so `withListedState` (`github/pull-state.js:108`) patches a cached record with
  the state the list saw later.
  That is a merge of two partial copies of one object, written for one field.
- **A facet already arrives by a lane of its own, matched by revision.** The change
  totals are read in batches for the rows in view, kept per document, and drawn only
  where their head and base match the ones a surface shows (`briefMatches`,
  `github/pull-summary-brief.js:67`). A total for another head is not older; it is about
  something else.

### Validation and SoftSchema Today

| Family | Declared as | Validated |
| --- | --- | --- |
| Tree, Recent, rollup | `TypedDict`s in `wire_models.py` | By tests only; the validators are not called on a response |
| Git | `TypedDict`s in `git/wire.py` | By tests only |
| `/api/file` | Dict literals | Not declared |
| GitHub records | Pydantic models with `extra="forbid"` and their own schema versions | On every read and write of a cache file |
| File Diff Format, File Rollup Format | A schema, a conformance corpus, and two implementations each | Both implementations run the corpus |
| Repository cache records | SoftSchema contracts | On every read and write |

SoftSchema is a first-party dependency, pinned and reviewed in
[SUPPLY-CHAIN-SECURITY.md](../../../../SUPPLY-CHAIN-SECURITY.md).
It names a contract with an identifier such as `metabrowser.cache:RepositorySource/v1`,
compiles a Pydantic model to a deterministic JSON Schema carrying a digest, and
validates in two layers, structural and semantic, at one of three maturities: `soft`,
`permissive`, and `enforced`. Metabrowser uses it for the repository cache:

- `cache/contracts.py` binds each contract to one model in `cache/records.py` and one
  compiled schema under `data/cache-format/`.
- `plugin_loader/artifact_contracts.py` holds a general registry
  (`build_contract_registry`, `validate_record`, `serialize_artifact`), and
  `plugin_loader/artifact_inventory.py` runs each contract’s corpus and round trip.
- `devtools/check_artifact_contracts.py` compares the installed contracts with the table
  in [Repository Cache](../../architecture/arch-repository-cache.md#record-contracts),
  in `make lint-check`.
- Importing `metabrowser` must not load `softschema`, `jsonschema`, or
  `frontmatter_format` (`tests/test_plugin_public_api.py:108`,
  `devtools/check_distribution.py:62`), so schema validation stays off the startup path.
  A server loads them on first use of the cache or a GitHub route, through the cache’s
  contract imports (`cache/atomic.py:26`, `:41`) and `github/pull_list.py:43`, which is
  why the GitHub sidekick imports its builders inside each handler
  (`github/sidekick.py:13`).

The registry is general, but only the cache declares contracts in it.

An earlier plan,
[A Machine-Readable Contract for the API Envelopes](plan-2026-08-30-api-schema-and-contract.md),
looked at describing what each route answers.
It closed one question, that envelopes stay internal, and recommended generating JSON
Schema from the `TypedDict`s. It set SoftSchema aside for envelopes, on the ground that
SoftSchema is for durable records, written now and read by a later release, while an
envelope is produced and consumed by one artifact in one request.
[Decision 1](#decision-1-what-describes-an-object) takes that reasoning up.

### The Plugin Surface Today

[Plugin System](../../architecture/arch-plugin-system.md) and
[Plugin Authoring](../../../plugins.md) describe the contract.
A manifest declares `[[kind]]` rules, `[[view]]` tabs, and `[[data_hook]]` routes
(`plugin_loader/manifest.py:164`, `:184`, `:275`); the browser side is
`mb.registerView(kind, viewId, {render, dispose})` (`static/plugin-sdk.js:479`).
`PLUGIN_SDK_VERSION` (`plugin_loader/manifest.py:43`) refuses a manifest written for
another SDK.

Four facts shape what follows:

- **The SDK has no list, row, or object primitive.** It offers formatters, icons, ref
  chips, and data fetches (`static/plugin-sdk.js:1802`), and drawings of parts of an
  object: `actorIdentity` for an author and `changeLine` for change totals.
- **One composition contract exists already.** Folder Overview panels register with
  `resolve`, `mount`, and `update`, and a composer owns order and layout
  ([Folder Overview Contributions](../../../plugins.md#folder-overview-contributions)).
- **A container is the one list a plugin supplies.** A kind declared with
  `container = { children = "<route>" }` answers
  `{children: [{name, path, badge?, muted?}]}`, and the tree draws those as rows
  ([Navigation Containers](../../architecture/arch-plugin-system.md#navigation-containers)).
- **Pull requests reach past the plugin boundary.** The Pulls tab’s host and the
  pull-request route are core modules (`static/pulls-nav.js`, `static/pull-route.js`);
  the tab registers through the internal `window.MetabrowserShell`
  (`static/pulls-nav.js:715`, `static/app.js:5120`); and Quick Search’s pull-request
  provider is in core (`static/search-controller.js:397`). Core names a GitHub concept
  because a plugin cannot yet supply it.

### Rules Any New Model Must Honor

- **Parity.** Every route and every model the browser consumes has a `metab` equivalent
  and a golden; data semantics, including membership, ordering, and bounds, belong to a
  route; browser-owned behavior runs browserlessly against production JavaScript
  ([AGENTS.md](../../../../AGENTS.md#cli-and-functional-ui-parity)).
- **Rows.** A row is one activation target at one height, on the shared row height and
  hover tokens ([Rows and Disclosures](../../../design-system.md#rows-and-disclosures));
  a pull request’s row is one link, so a new tab and a copied address are the browser’s
  own ([Rows](../../../design-system.md#rows)), and its change line is a second target,
  its one child, which toggles its files and opens no page
  ([The Pulls Tab](../../../design-system.md#the-pulls-tab)).
- **Text by role.** Navigation rows and the pane each have one body size, and metadata
  takes the size of the text it accompanies, in muted ink
  ([Text Roles](../../../design-system.md#text-roles)). A new shape’s lines follow it.
- **Stable boxes.** A region’s box is decided at first paint, and data that arrives
  later fills a reserved slot
  ([Regions Keep Their Boxes](../../../design-system.md#regions-keep-their-boxes)); in
  the Pulls tab, rows already drawn never move without input
  ([The Pulls Tab](../../../design-system.md#the-pulls-tab)).
- **Folder views are tabs.** The design system already places a future **Files** listing
  beside Overview and Treemap
  ([Folder Views Are Tabs](../../../design-system.md#folder-views-are-tabs)).
- **Measured bounds.** A limit records the measurement that set it, and virtualizing is
  the last rung of the ladder
  ([Rendering Large Content](../../../large-content-rendering.md)).
- **Fast by default.** A return to anything already shown makes no data request, and the
  work a click waits on is prepared before the click
  ([Instant Transitions and Stable Layout](plan-2026-11-11-ui-apparent-performance.md));
  loading chrome does not appear inside the shared quiet period
  ([Loading Chrome](../../../design-system.md#loading-chrome)).
- **Loading tiers.** New shell code is not eager unless the first render is wrong
  without it
  ([Asset Loading Tiers](../../architecture/arch-browser-shell.md#asset-loading-tiers)).
- **One artifact.** The server, shell, and built-in plugins change together, so an
  internal shape changes everywhere in one commit, with no second reader
  ([Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code)).

### Prior Art

- **Identity.** GraphQL’s
  [global object identification](https://graphql.org/learn/global-object-identification/)
  gives every object an identifier that suffices to fetch it again, which is what lets a
  client cache by identity.
  [JSON:API](https://jsonapi.org/format/) identifies a resource by `type` and `id`
  together and refers to related resources by that pair.
- **A normalized store.**
  [Redux’s guidance](https://redux.js.org/usage/structuring-reducers/normalizing-state-shape)
  keeps each item once, by identifier, and holds a list as an ordered array of
  identifiers, so an update is made in one place.
- **A view declares the fields it reads.**
  [Relay](https://relay.dev/docs/principles-and-architecture/thinking-in-relay/) has
  each component declare its fields as a fragment and see only those, while one query
  fetches for the whole tree of components.
- **A list host that draws the rows.** In VS Code’s
  [Tree View API](https://code.visualstudio.com/api/extension-guides/tree-view) an
  extension supplies data elements and a `TreeItem` describing each row (label,
  description, icon, collapsible state), and the host draws it.
- **List and detail of one object.** GitHub’s GraphQL API has one
  [`PullRequest`](https://docs.github.com/en/graphql/reference/pulls) type, carrying
  `reviewDecision`, `statusCheckRollup`, `comments`, `additions`, and `changedFiles`,
  whether it is reached through a list or by number.
  Its pull request list filters by review status, check status, author, and labels, and
  sorts by update time or comment count
  ([GitHub Docs](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/filtering-and-searching-issues-and-pull-requests)).
- **A mixed timeline.** A pull request’s timeline in the same API is a union of item
  types told apart by a type name.
  [ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/) models an activity
  stream as an ordered, paged collection whose items embed an object or refer to it by
  identifier.

### What the Background Shows

1. The model layer is shaped by surfaces: each route and panel has its own copy of each
   object, with its own field names.
2. Two surfaces already separate description from paint, and one already draws a single
   component at two sizes.
   Below the row, the sharing has begun: one page header, one author, and one change
   line serve the commit and pull request surfaces.
   Rows and lists are still built per surface.
3. The stores keep what a surface draws, so a second surface cannot reuse them, and a
   row and its page are reconciled by hand.
   The one exception, the change totals, shows the shape a facet takes in practice: its
   own batched route, its own memory, and a match by revision, not by age.
4. List mechanics (windowing, roving focus, paging, arrival) are implemented per list
   and kept consistent by tests over source text.
5. The contract machinery for a named, versioned, corpus-checked model exists and has
   one user.
6. A plugin can add a kind, a tab in the pane, a data route, and an Overview panel, but
   not a row, a list, or a navigation panel, which is why pull requests live partly in
   core.

### Work in Flight

Pull requests and planned work that touch this plan, as of 2026-11-18. Each changes what
a phase builds on, so a phase starts from whatever of it has landed.

| Work | What it does | Bearing on this plan | Before Phase 1? |
| --- | --- | --- | --- |
| [#550](https://github.com/jlevy/metabrowser/pull/550) and [#552](https://github.com/jlevy/metabrowser/pull/552) | One view header for files and folders, `viewHeaderHtml(parts)` over `MetabrowserViewHeaderParts{path, eyebrow, iconHtml, title, line}`, which also writes the header’s corner, `.view-header-end`; `mtime` on `/api/file`; a GitHub control in that corner | The `page` shape’s frame for all four types; a time on the file envelope ([Decision 7](#decision-7-the-shared-header), [Decision 8](#decision-8-timestamps)) | Merged on 2026-11-18, after the `a1100bca6` this plan was revised against; the header’s builders are in an on-demand `view-header` bundle |
| Bead mb-7t5s | Moves the pull request and commit pages onto the view header | The SDK frame through which a plugin draws the header, which [Decision 12](#decision-12-how-a-view-is-defined) decides it builds | Not started; it lands before the `/pulls` page |
| [#380](https://github.com/jlevy/metabrowser/pull/380) | Plugin sources and out-of-process environments: one `sdk_version` under a caret rule, read before schema validation; third-party Python in a worker | How a manifest block versions ([Decision 20](#decision-20-plugin-declaration-and-the-sdk-gate)); whether the host can import a plugin’s model ([Plugins](#plugins)) | Unlikely; a draft awaiting the owner’s decisions |
| [#534](https://github.com/jlevy/metabrowser/pull/534) | Opening any target from the CLI, the skill, and the macOS app; its code landed in #539 and #540 | Agrees with [Decision 5](#decision-5-identity) A; adds spellings of a kind, which that decision renames to the type tokens | Merged on 2026-11-18; the code is on `main` |
| The macOS app plan’s Phase 3: beads mb-1zyp, mb-54r1, mb-idri, and the live-server registry mb-5xi4 | Host mode’s `present` and `clients` verbs, the `navigate` event its pages follow, an agent front door, and a registry that finds a root’s running server | The view model supplies their payloads and names ([Reading](plan-2026-11-18-view-model-and-view-state.md#reading)); reading a running server from ROOT, and every change to `--present`, wait on the registry | No; planned, not started |
| [#498](https://github.com/jlevy/metabrowser/pull/498) and its stack (#501 to #503, #507, #508, and #518 to #520) | fdu as an inventory provider; #507 records decisions D1 to D22 in [Inventory Provider](../../architecture/arch-inventory-provider.md) | File and folder identity, completeness, removed subtrees, and a retryable tree answer, for [Phase 2](#phase-2-core-types-and-the-folder-page) | No; drafts, Phase 2 only |

## Design

### Approach

Add one layer beside the four that exist, and adopt it one surface at a time.

```text
feeds                     objects                      views
────────────────────      ─────────────────────        ───────────────────────────
routes and events    ──►  one model per type,     ──►  nav row · wide row · card
(compact or full)         held once by identity        (one object, several shapes)
        │                         │
        └─ one adapter per feed   └─ collections: ordered references, paged,
           into the object           with freshness, drawn by one list host
```

| Term | Meaning |
| --- | --- |
| **Object** | A thing with an identity that Metabrowser shows: a file, a folder, a commit, a pull request |
| **Type** | What an object is. A type has one contract. Not a kind: a `file` has many kinds |
| **Summary** | The fields every object of a type always carries: enough for any row or card |
| **Facet** | A named, optional group of further fields, present whole or not at all: a description, change totals, checks |
| **Reference** | `{type, id}`, and for a nested object `{type, id, parent}`, where `parent` is the reference of the object it sits in: enough to name an object without holding it. It carries no title and no other field of the object |
| **Collection** | An ordered list of objects from one source, with a cursor and a freshness |
| **Collection reference** | `{name, params}`: a registered collection’s name and the parameters that select one list of it; a parent’s collection adds `parent`, the parent’s reference. It is data, as a reference is, and not the store’s **collection handle**, the live object it resolves to ([Browser Data Model](#browser-data-model)) |
| **Shape** | A named form a view takes: `nav-row`, `wide-row`, `card`, or `page` |
| **View** | The drawing of one type in one shape |
| **Feed** | A route or event stream that supplies objects, in whatever encoding its cost allows |
| **Slice** | A step of delivery, and never a part of a record. The **object slice** is the object model’s first step ([Decision 22](#decision-22-the-first-slice)) and the **view slice** the view model’s ([Decision VM-10](plan-2026-11-18-view-model-and-view-state.md#decision-vm-10-the-view-models-first-slice)) |

The reference and the collection reference are defined here once, and the object model
and the view model both use them as defined.

Several existing names sit near these and mean something else.

- The **Git Commit Summary** component is, in these terms, a commit’s page header and
  its card.
- A kind’s `[[view]]` is a view in the `page` shape, called a **page view** below.
- The server’s **view** is what it shows now, a folder’s working tree or one revision
  ([Open Modes](../../architecture/arch-open-modes.md)). This plan says “the served
  revision” for that, and keeps “view” for a drawing.
- **Recent** already names two things: the Files tab’s Recent view over `/api/recent`,
  and the recent targets `metab --recent` keeps for the macOS app’s Open Recent
  ([Recent Targets](../../architecture/arch-recent-targets.md)). The Recent tab of
  [Decision 19](#decision-19-where-recent-changes-lives) is a third, and the Recent tab
  plan’s [RT-6](plan-2026-11-18-recent-tab-updates-and-events.md#rt-6-the-name) retires
  the name from the Files view.
- The **view header** (#550) and the **page header** (#487) are drawings of the shared
  header below, in the `page` shape.

The design rests on five rules:

1. **A view receives an object and nothing else.** It learns neither the route nor the
   store, which is the existing rule that a view never learns its source, extended from
   pages to rows.
2. **Every row and card can draw from the summary.** Any collection can therefore be
   drawn in any summary shape with no further request.
   A view may name facets it would use; it draws without them and fills a reserved slot
   when they arrive.
3. **The contract describes the object, not the feed.** A bulk feed may stay compact
   where its cost was measured, as the catalog and the tree are.
   Each feed has exactly one adapter into the object.
4. **The host owns the list; the type owns the row’s content.** Windowing, keyboard,
   disclosure, paging, and arrival are written once.
5. **An existing surface moves onto the model only behind a measurement.** New surfaces
   are built on it first.

### Components

| Component | Where | Job |
| --- | --- | --- |
| Object models for core types | `objects/` (new package) | Pydantic models for the reference and the collection reference, the header, shared sub-objects, `File`, `Folder`, and `Commit`; the projection from each existing record |
| Compiled schemas and corpus | `data/object-format/` | One schema per contract and one conformance corpus, packaged in the wheel |
| Object registry | `objects/registry.py`, declaring into `plugin_loader/artifact_contracts.py` | Types, contracts, collections, and views a build registers; the source for `/api/object-types` and the checks |
| GitHub object types | `github/objects.py` and the plugin’s manifest | `PullRequest`, later the comment types; projections from `PullListRow` and `PullRecord` |
| Object store | `static/object-store.js` | `get`, `subscribe`, `ensure`, and `collection` to read; `registerType`, `registerCollection`, and `put` to declare and write; a source per type |
| List host | `static/object-list.js` | One windowed, keyboard-navigable list for any collection in any shape |
| SDK surface | `mb.objects`, registered in `static/plugin-sdk-views.js` | `registerView`, the store’s read and write calls, and `mountList` |
| Views | The `folder` plugin for files and folders, the shell for commits, the `github` plugin for pull requests | `describe` and `paint` for each type and shape |

The view model’s components, the `ui/` package, `static/ui-state.js`, and `mb.ui`, are
listed in
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md#components).

### Object Model

#### Types, Identity, and the Header

Every object carries a small header, the same for every type:

| Field | Meaning |
| --- | --- |
| `type` | The registered type: `file`, `folder`, `commit`, `pull-request` |
| `id` | A string unique within the type and its scope, described below |
| `href` | The object’s address in the browser; a type with no page of its own is addressed inside its parent’s page |
| `title` | What a row leads with: a file’s name, a commit’s subject, a pull request’s title |
| `updated_at` | When the object last changed, or null when unknown, which counts as older than any time; a mixed list orders by it |
| `actor` | Optional: who is responsible, as `{name, login?, avatar_url?}` |

`type` and `id` together are the identity, and the store’s key.
The identifier is the one each type already uses:

| Type | `id` | `href` | `updated_at` |
| --- | --- | --- | --- |
| `file` | The canonical inventory path, or the `GitPath` wire on a pinned revision | `/view/<id>` | Modification time; null on a pin |
| `folder` | The same path space | `/view/<id>` | Newest modification beneath it; null while totals are pending |
| `commit` | The full commit ID | `/commit/<id>` | Commit time |
| `pull-request` | The number, as a string | `/pull/<id>` | GitHub’s `updated_at` |

The Recent tab plan adds three core types: `working-tree-changes`, a checkout’s
uncommitted changes, with the one `id` `working-tree` and the address `/status`
([Working-Tree Changes](plan-2026-11-18-recent-tab-updates-and-events.md#working-tree-changes));
and `update` and `event`, the rows of the Recent tab
([Contracts](plan-2026-11-18-recent-tab-updates-and-events.md#contracts)).

These four `type` tokens are the one vocabulary for what a target is, by
[Decision 5](#decision-5-identity), taken on 2026-11-18. Two vocabularies on `main` name
a target differently today, `--present`’s `kind` (`cli/present.py:126-128`) and a
selection’s `SelectionKind` (`cache/urls.py:77`), and both are renamed to the type
tokens:

| Object `type` | `--present`’s `kind` today | `SelectionKind` today |
| --- | --- | --- |
| `file` | `file`, locally and on GitHub | `blob` |
| `folder` | `folder` locally, `tree` on GitHub, and `repository` for a repository’s root | `tree`, `repository` |
| `commit` | `commit` | `commit` |
| `pull-request` | `pull_request` | `pull_request` |

So `blob` becomes `file`, `repository` and `tree` both become `folder`, and
`pull_request` becomes `pull-request`. A `type` says what a thing is and not where it
came from, so the two vocabularies lose a fact the kind carried: a repository’s root
with no ref named is not a named tree.
A separate field keeps the two apart, as Decision 5 records.

The address is a function of the identity through the encoders that exist
(`view_routes.py`, `static/navigation.js`, `static/pull-route.js`, and on the Python
side `selection_view_href` in `cli/selection_href.py:16`), which the
`navigation.route-identity` parity row already pins.
The function has an inverse: a core type with a page of its own registers both
directions, `href(id)` and `parse(address)`. A plugin cannot register an address
([Non-Goals](#non-goals)), so a plugin type’s page is a kind’s page at a `/view/`
address, and that address still parses to a `file`, by the plugin authoring plan’s
[Decision PS-5](plan-2026-11-18-plugin-authoring-objects-views.md#decision-ps-5-a-type-whose-objects-are-files).
The parsers exist: `parse` and `parseCommit` (`static/navigation.js:210`, `:39`),
`parsePull` (`static/pull-route.js:83`), and the server’s decoders in `view_routes.py`.
So `--show`’s `object:` line and a view state’s `object` are the same reference for one
address, and an intent that names an object opens what one that names its address opens.
A GitHub object also has a web address, which `GithubUrlReducer.web_url` builds
(`github/urls.py:560`) and which #552 draws at the end of the view header; whether the
header carries it is an [open question](#open-questions).
A type with no page of its own, such as a comment once it is one, is addressed as its
parent’s address plus a fragment, which the
[URL grammar](../../architecture/arch-views-models-routes.md#browser-url-grammar) leaves
to the document. So every object a collection can hold has an address, and every row the
list host draws is a link.
An identity is scoped by its type’s source: the served root and the served revision for
files, folders, and commits, and the repository and signed-in reader for pull requests.
Since #559 a repository folder can switch between its working tree and a revision of its
own checkout (`POST /api/source/pin`, guarded by `pin_changed`), so the served revision
is a scope for a plain repository folder too, not only for a mirror.
When a scope changes, the store drops that type’s objects, as the pin guard refuses
requests for another pin today.

#### Summary and Facets

One contract per type declares the summary as required fields and each facet as an
optional sub-object.
A facet is present whole or absent; a view never tests single fields of one.

| Type | Summary, beyond the header | Facets |
| --- | --- | --- |
| `file` | `ext`, `logical_ext`, `size`, `kind` when classified, `gitignored`, compression, and on a pin `display_path`, `mode`, and `oid` | None. The page is the `/api/file` envelope |
| `folder` | `totals{files, bytes, unignored_files, unignored_bytes, complete}`, `gitignored`, `empty` | `readme{path}`, `types` (the rollup’s leading types) |
| `commit` | `short_id`, `authored_at`, `parent_ids` | `refs`, `message{body}`, `changes` (change totals) |
| `pull-request` | `number`, `state` (one of open, draft, merged, closed), `created_at`, `closed_at`, `merged_at`, `base{ref}`, `head{ref, repository, sha}`, `labels` | `description{body, truncated}`, `merge{mergeable, merged_by, commits}`, `stack{number, position, total}`, `checks`, `changes` (served today by `pull-files-summary`, for a head and base) |

The field lists are a sketch grounded in today’s models; the model written against a
corpus settles them.
The corpus is shaped like cached records and written by the production writers from the
synthetic fixture accounts, never copied from a real cache: a cached row carries GitHub
users’ logins, avatars, titles, and labels (`github/pull_list.py:99`), which
[AGENTS.md](../../../../AGENTS.md#documentation-and-public-hygiene) forbids committing.
`tests/test_github_drawn_from_disk.py` already builds such a cache home for the GitHub
plugin: record, catalog, changed-files lists, stacks, labels, timeline, core, and
manifest, through the production writers (`_build`, `:314`). Its `ELEMENTS` table
(`:566`) maps each drawn element to the route that answers it, which is close to a table
of where each summary field and facet comes from.
The pull request corpus starts there; the core types’ corpus starts from
`tests/cache_home_fixture.py`. Three choices in the sketch are deliberate:

- **One state for a pull request,** derived in the projection
  ([Decision 10](#decision-10-how-far-a-contract-normalizes-its-source)).
- **One spelling for each sub-object.** `base` and `head` take the record’s nested form,
  with what a catalog row lacks left to a facet, and an author is an `actor`.
- **A commit’s refs are a facet.** Refs move while the commit does not, so they carry
  the history’s generation and not the commit’s time.

Five places where the sketch does not yet fit the records are open items for the corpus
work, settled before each contract is written:

- **The base side’s commit and repository.** `base` keeps only `ref` in the summary, and
  no facet yet holds the record’s `base.sha` and `base.repository`
  (`github/pull_record.py:176`, `:216`).
- **Unknown and partial change totals.** A commit at a shallow boundary has every count
  null (`git/wire.py:243`), while File Diff Format’s `Totals.files` is a required count
  (`diff/format.py:170`), so the one change-totals sub-object must be able to say
  “unknown”. `ChangeSums` adds a third state, `short`, for a list that stopped before its
  end (`github/pull_change_sums.py:38`), and `FilesSummaryWire` makes each count
  nullable (`github/pull_files_summary.py:98`). The sub-object starts from those two and
  from what `changeLine` draws, an unknown count as “?”, rather than from a new shape.
- **The facet’s key.** A `changes` facet describes one head and base, not a moment.
  It carries them, and a surface draws it only for the head and base it shows, as
  `briefMatches` does today (`github/pull-summary-brief.js:67`).
- **An empty folder’s time.** A finalized empty folder’s time is `0.0`, which differs
  from the null of a pending one (`wire_models.py:34-39`); under
  [Decision 8](#decision-8-timestamps) A, the mapping to `updated_at` must keep that
  difference.
- **Labels.** A catalog row carries label names (`github/pull_list.py:120`) and a record
  carries `{name, color, description}` (`github/pull_record.py:163`), so the summary’s
  `labels` must take one form and leave the rest to a facet.

#### Nesting, References, and Sub-Objects

Three levels of modeling, chosen by what a thing must do:

| Level | Has | Examples | Modeled as |
| --- | --- | --- | --- |
| Top-level object | Identity, a contract, views, usually a page | File, folder, commit, pull request | A registered type |
| Nested object | Identity within a parent; no page of its own | Comment, review, check run, changed file, ref | A facet’s items at first; promoted to a registered type, addressed inside its parent’s page, when it must appear in a collection outside its parent |
| Sub-object | No identity | Actor, change totals, branch side, folder totals, label | A shared definition that every contract reuses |

- **Containment is a collection on the parent.** A pull request’s commits, discussion,
  and changed files are collections named on it, not arrays inside its summary.
  Each is named by a collection reference that carries `parent`, the parent’s reference,
  such as `{name: files, parent: {type: pull-request, id: "561"}}`, and its `name` is
  unique within the parent’s type.
  The routes that serve them today (`pull-timeline`, `pull-files`) keep their shapes
  until the page adopts the model in Phase 3.
- **A reference is the same everywhere,** as [Approach](#approach) defines it: in the
  order a collection holds, a timeline, a Quick Search result, and a view state.
  The timeline route is the precedent: it refers to comments and reviews by kind and
  identifier, though it embeds each commit’s subject and time
  (`github/pull_timeline.py:74`, `:81`). A reference names an object; it does not
  promise the served source can open it, and a fork’s commit may be absent from a served
  checkout, as it is today.
- **A nested object’s reference names its parent.** A nested identifier may be unique
  only inside one parent, as a changed file’s path is unique only inside one pull
  request or one comparison, so `{type, id}` alone cannot leave the parent.
  Its reference adds `parent`:
  `{type: changed-file, id: <path>, parent: {type: pull-request, id: "561"}}`. Two
  places hold a nested reference outside its parent’s page: a view state’s `pane.inner`,
  and a member of an update in the Recent tab, where the first such member is a
  `changed-file` of `working-tree-changes`.
- **A sub-object has one definition.** Change totals,
  `{files, additions, deletions, exact}` with optional per-status counts, serve a
  commit, a pull request, a stack, and a changed file’s line counts, in place of the
  shapes there are now.
  Its drawing exists, `changeLine`, and so does an author’s, `actorIdentity`; each
  sub-object’s definition is written to what its drawing already takes.

#### Extension Path

| Candidate | Owner | Becomes a type when |
| --- | --- | --- |
| Comment, review, review comment | GitHub plugin | The Recent tab lists a comment as an update’s member; until then an update counts comments without listing them |
| Check run | GitHub plugin | A checks list appears outside the pull request page |
| Stack | GitHub plugin, from `github/pull_stacks.py` and `stack-change` | A stack is listed or linked outside the Pulls tab; its heading already draws its own change totals |
| Branch, tag | Core, from `GitRef` (`git/wire.py:69`) or the chooser’s `SourceRef` and `WorkingTree` (`source_routes.py:246`, `:261`) | Now: #559’s branch and tag chooser is a branches list, with a second model of a ref beside `GitRef`; the type picks one of the two |
| Changed file | Diff plugin, from File Diff Format’s file entry | A changes list is drawn outside a comparison. Its row is not always a link: “View on branch” is a link only where the served revision is the diff’s head, and otherwise a button that switches the revision first (#511) |
| Issue | GitHub plugin | Issues are added at all |
| Agent session | The `agent-log` plugin | Sessions are listed |

A new type is a contract, a projection, and a feed.
With no view of its own it still draws in every summary shape from its header; a view is
added where the header is not enough.
Issue comments, reviews, and review comments have separate identifier spaces
(`github/pull_record.py:221`, `:233`, `:246`), so they become three types, or one whose
`id` carries the kind; the comment model settles which.

### Contracts

**Where they live.** Core types are Pydantic models in `objects/`, compiled to
`data/object-format/schemas/` under identifiers such as `metabrowser.objects:File/v1`. A
plugin’s types live with the plugin: `metabrowser.github:PullRequest/v1` beside the
GitHub plugin’s other models.
Shared sub-objects are definitions in one module that each contract includes.
The reference and the collection reference are two of them, and the `metabrowser.ui`
family includes the same two
([UI Contracts](plan-2026-11-18-view-model-and-view-state.md#ui-contracts)).

**What the registry needs.** A declaration in `plugin_loader/artifact_contracts.py`
names an artifact profile, an envelope key, producers, consumers, and a corpus (`:64`),
and the registry admits only the `pure-yaml` profile and only `enforced` artifacts
(`:311`, `:399`). Object contracts declare that profile with the envelope key `object`.
Objects travel as JSON and are validated as records, through `validate_record`, in the
tests and the CLI and never on a running server; the profile is the form an object takes
if it is ever written out, which the CLI could do.

**What is not a contract.** The transport around objects stays an internal envelope, as
the envelope plan decided.
A collection’s envelope follows a small convention the store relies on, checked by
tests: `rows`, `next_after`, `complete`, `truncated`, and `generation`, beside whatever
else the route answers ([Decision 3](#decision-3-the-collection-envelope)). The files a
plugin keeps in the cache stay its private format, with their own schema versions; a
projection maps a record to an object, so a cache format and a served model change
independently.

**How they version.** The identifier’s version changes on a break: a field removed,
renamed, or retyped.
An added optional field is not a break.
There is one reader per contract, in the same artifact, so a version is an identity and
never a negotiation, the standing answer for file formats in
[Compatibility and Legacy Code](../../../development.md#standing-compatibility-answers).
A break in a *core* type a plugin reads is a break in the SDK, and moves
`PLUGIN_SDK_VERSION` with every built-in manifest.

**How they are validated.**

| Where | Check |
| --- | --- |
| Authoring | A model and its committed schema are compared by the test suite, `metab --doctor`, and the wheel check, as `check_packaged_schemas` is for the cache (`cache/contracts.py:252`) |
| Corpus | Each contract has positive and negative cases; `devtools/check_artifact_contracts.py` runs them and the round trip in `make lint-check` |
| Producers | A test drives every branch of every projection and validates the result, as `wire_models.py` asks of the tree today |
| Goldens | `--api` validates the `rows` of a declared collection route, *before* normalization, and a failure fails the command, so every `--api` golden over such a route is contract evidence |
| A running server | No response is validated ([Decision 16](#decision-16-runtime-validation)) |
| Browser | The strict normalizer each type registers, run at the store’s boundary in the manner of `builtin_plugins/diff/diff-model.js` and browserlessly over the same corpus; declarations in `static/types.d.ts` generated from the schemas and checked for drift |

The golden row answers a problem the envelope plan left open, that a transcript is
normalized and cannot be parsed back: the command validates what the route answered, not
what it printed.

### Views

#### Shapes

| Shape | For | The host’s frame | Draws from |
| --- | --- | --- | --- |
| `nav-row` | A navigation panel | One link; the shared row height, hover, and current marks; up to three lines; may own a facet line as its one child, which may own a child group | Summary; named facets in reserved slots |
| `wide-row` | A list in the main pane | One link in a grid: leading mark, title line, metadata line, trailing columns | Summary; named facets in reserved slots |
| `card` | A timeline or a hover | A bordered box on `.page-card`: title, byline, and a bounded body | Summary; named facets in reserved slots |
| `page` | The pane | The shared view header (#487, #550), then the kind’s `[[view]]` tabs | The header from the summary; the body from the page’s own model |

The Pulls row sets the `nav-row` frame: a container whose one child is its change line,
at the row’s level plus one, which owns the changed files at plus two
([The Pulls Tab](../../../design-system.md#the-pulls-tab)). A shape that allowed only “a
row that may own a child group” could not express it.
The metadata line of a `wide-row` follows the view header’s line rules from #550: the
age last, and an item that does not fit leaves the line whole.

The set is closed and owned by the host, because a shape is a contract with the list
host about height and activation ([Decision 11](#decision-11-the-set-of-shapes)). `card`
is named in the set now, and its frame is built with its first real use.
Two more are visible in today’s code and left for later: a Quick Search option, and an
inline mention such as a ref chip.

#### One Model, Several Views

A view is registered for a type and a shape, in two parts:

```javascript
// Pure: an object in, plain data out. Runs browserlessly.
function describePullWideRow(object, context) {
  return { title: object.title, state: object.state /* … */ };
}

// Fills the host's frame, and patches it when the description changes.
function paintPullWideRow(frame, description) {
  return { update(next) {}, dispose() {} };
}

mb.objects.registerView("pull-request", "wide-row", {
  describe: describePullWideRow,
  paint: paintPullWideRow,
});
```

The facets a view reads are declared in the manifest, as `facets = ["stack"]` on its
`[[object_view]]`, and the list host requests them for the rows in view
([Decision PS-1](plan-2026-11-18-plugin-authoring-objects-views.md#decision-ps-1-where-structure-is-declared)).

- **`describe` is the tested half.** It is what `describeRow` is today: every decision
  about what a row says, as data.
  A browserless session prints each registered view’s description of each corpus object,
  which makes a view’s content a golden.
  It is a named function, because `devtools/check_parity.py` credits a session by the
  functions it ran.
- **`paint` owns only the inside of the frame.** The host creates the activation target
  and sets its link, roles, tab stop, and current mark, so one-link rows, roving focus,
  and the row tokens hold for every type without each view restating them.
- **A fallback covers every pair.** A type with no view for a shape draws from its
  header: a type icon, the title, the actor, and the age.
- **Collection context is not object data.** A commit’s graph lanes depend on its place
  in a page of history, not on the commit.
  The list passes such context to the view beside the object.
- **Registering costs nothing at load.** `registerView` and `registerType` record what
  they are given and load nothing.
  They sit with the SDK’s view helpers in the `sdk-views` bundle, which loads before any
  plugin code (`static/plugin-sdk-views.js:11-16`), and the store is in that bundle too;
  the list host is a bundle of its own.
  [Performance](#performance) states each tier and why.

The narrow and wide rows of a pull request are then two descriptions of one object.
The wide row has room for what the narrow one omits and the summary already holds:
labels, the opened and closed ages, and both branch chips.
It also draws what the narrow row now draws from a facet, the change line, from the same
lane, so the wide row never says less than the narrow one.
A commit’s card is the compact commit summary: its subject, author, age, and revision
come from the summary, and its two change-totals rows hold their height until the
`changes` facet arrives.

#### The List Host

`mb.objects.mountList(container, {collection, shape, …})` draws a collection.
It returns a handle at once, with a `ready` promise and a `dispose`, since the host is a
bundle loaded on demand; the plugin authoring plan’s
[JavaScript SDK](plan-2026-11-18-plugin-authoring-objects-views.md#javascript-sdk) gives
its signature and lifecycle.
The host owns:

- **Windowing.** Variable-height rows over a spacer, generalizing
  `github/pulls-window.js`, with the current and focused rows kept mounted.
  A short list is drawn whole.
  Each use records its measured estimate and overscan beside its constants.
- **Keyboard and activation.** One Tab stop and roving focus.
  A row is a link to the object’s `href`, and a modified click is the browser’s. Whether
  moving opens a row, and whether opening pushes or replaces the history entry, are
  options the surface sets, because the three navigation collections differ on purpose
  ([Navigational Row Collections](../../../design-system.md#navigational-row-collections)),
  and a list in the pane differs again
  ([Decision 21](#decision-21-keyboard-contract-for-a-list-in-the-pane)). The host joins
  the registry that `test_nav_like_row_sets_share_the_vertical_keyboard_contract`
  maintains.
- **Disclosure.** A row may own a nested collection drawn under it, as a folder owns its
  children and a pull request its changed files.
  The host owns the chevron, the expanded state, and the child group, and asks whether a
  row owns one, as the tree does, and where the disclosure sits: on the row, as a
  folder’s is, or on a facet line under it, as a pull request’s change line is.
  The keyboard follows the place: Right on a row with a facet line moves to that line
  and opens nothing, and Up and Down never expand.
- **Loading.** Rows paint from the store when the collection is held.
  A cold list shows row-shaped skeletons after the shared quiet period, never a spinner
  over rows.
- **Paging and arrival.** The host asks the collection for more near the tail.
  Rows that arrive late are offered, not inserted under the reader, and a new row takes
  the shared arrival highlight.
  A row whose object changes is repainted where it is, through its view’s `update`, and
  a collection’s new order is applied only on the reader’s input, which the Recent tab’s
  live rule relies on
  ([Clumping](plan-2026-11-18-recent-tab-updates-and-events.md#clumping)).
- **Sections.** A list may group consecutive items under headings: days in a timeline,
  stacks in the pull list.
  Which items share a section is a pure function over the items, tested as `describe`
  is. A heading is more than a label, though: a stack’s heading reads its own data, the
  stack’s change line from `stack-change`, and a section can change its rows’ indent, as
  a stacked pull request sits one slot in (#506). So a section has a `describe` of its
  own, and may name a facet of the section, as a row names one of its object.
- **The collection’s own facts.** Counts, filters, and freshness belong to the
  collection handle, so the wide list and the Pulls tab show one filter and one set of
  totals.
- **State.** The host’s state is one serializable record, taken at mount and reported on
  change: the collection reference, the shape, the focused row, the expanded rows, the
  closed sections, and the first and last rows in view.
  That record is the **list facet** of a view state
  ([The View State](plan-2026-11-18-view-model-and-view-state.md#the-view-state)), so a
  list on the host is published with no code of its own.
  It replaces each panel’s own memory as panels converge: `navPanelScroll`
  (`static/main-tabs.js:118`), `closedStacks` (`github/pulls-panel.js:863`), and the
  tree’s DOM classes (`static/tree-expansion.js:125`). It also gives every browserless
  list session one thing to print.

#### Pages That Show Several Objects

A page is an ordinary page view of a kind, under the shared view header, and it mounts
one list host or several
([Decision 17](#decision-17-composing-a-page-of-several-lists)).

- **The pull requests page** mounts the pull request collection as wide rows, and may
  section it by stack.
- **A folder’s Files view** mounts the folder’s children: subfolders, then files.
  A subfolder’s wide row is where the folder is broken down: its file count and size,
  its newest change, and its leading file types, from its totals and its `types` facet.
- **The `/recent` page** mounts the Recent tab’s mixed collection as cards under day
  headings. It is the pane’s drawing of the list the tab draws as rows, and the Recent
  tab plan builds it last, in its R4.

#### Mixed Lists

A collection may hold several types.
The list host draws each item with the view for its type and the list’s shape, or the
fallback.

A mixed list is composed on the server, because membership and order are data semantics
and must be reachable through `metab`
([Decision 18](#decision-18-composing-a-mixed-list)):

- **Order.** The route merges its sources by `(updated_at, type, id)`, descending, which
  is a total order, so paging by it neither repeats nor skips an item that did not
  change between requests.
  A mixed list that admits unknown times sorts them after every known one, as the
  oldest, by `(type, id)`.
- **Paging.** The cursor is the last item’s position in that order.
  New items appear above the first page and are offered, not inserted.

The first mixed list is the Recent tab’s collection, and
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md) owns everything
particular to it: its sources and what each can answer today
([Tiers and Sources](plan-2026-11-18-recent-tab-updates-and-events.md#tiers-and-sources)),
how changes form its rows
([Clumping](plan-2026-11-18-recent-tab-updates-and-events.md#clumping)), what it says
about a source’s coverage, and its name beside the two things already called Recent.

### Browser Data Model

One interface, with the backing each type needs.
Views, pages, and the list host read; a type’s owner registers and writes:

```javascript
// Read.
mb.objects.get(ref)                         // the object in memory, or undefined
mb.objects.subscribe(ref, listener)         // called when that object changes
mb.objects.ensure(ref, { facets, signal })  // load facets; joins a read in flight
mb.objects.collection({ name, params })     // a collection reference in, a handle out:
                                            // rows, freshness, more(), subscribe()

// Register and write.
mb.objects.registerType(type, { normalize, load })  // its normalizer; how to load an object or facet
mb.objects.registerCollection(name, collection)     // a collection's rows, freshness, and more()
mb.objects.put(object, { feed, generation })        // hold a summary or facets, by the merge rule
```

- **Which calls are the SDK’s.** All seven are on `mb.objects`, with `registerView` and
  `mountList`, so a plugin type can supply its source and its normalizer and not only
  declare itself on the server.
  A type is registered once, by the plugin whose manifest declares it, and a collection
  by the plugin that declares it; a second `registerType` for one type, or a
  registration no manifest declares, is refused with a console warning.
  The manifest blocks arrive in Phase 2, by [Decision 22](#decision-22-the-first-slice),
  so the check against a manifest starts there, and Phase 1’s registrations are held
  only to one per type.
  The file and folder sources are host-private: the shell registers them through its
  internal seam, and no plugin can.
- **Every type ships its normalizer.** `registerType` requires `normalize`, and `put`
  runs it at the store’s boundary, so a plugin type brings its own strict normalizer, as
  `builtin_plugins/diff/diff-model.js` does for File Diff Format.
- **A source per type.** A type registers how its objects are held and loaded, through
  `registerType`. Commits, pull requests, and plugin types use a default table keyed by
  `id`, bounded per type at a measured size.
  A type or a collection whose manifest declares a route needs no loader of its own: the
  store reads the route by the collection convention, and `load` and
  `registerCollection` are for a controller of the plugin’s own
  ([Decision PS-2](plan-2026-11-18-plugin-authoring-objects-views.md#decision-ps-2-default-loaders-and-collections)).
  In the browser “source” means only this.
  A collection is registered with `registerCollection` and has no source of its own, and
  the server’s `[[collection_source]]` is a different thing: a source of the Recent
  tab’s mixed list, which answers changes, each `{subject, at, kind}`, and declares its
  kinds
  ([Updates and Events](plan-2026-11-18-recent-tab-updates-and-events.md#updates-and-events)).
- **Files and folders are adapters, registered by the shell.** `fileStore` is private to
  `static/app.js`, so the shell registers the source and a plugin reads through
  `mb.objects`. An object is built on demand from what is held, so a large tree
  allocates nothing per file.
  Three shapes are adapted: an event-stream entry, within the stream’s depth scope; a
  `/api/tree` node, for a deeper folder; and a pinned revision’s row, where there is no
  stream.
- **A folder’s children are a route’s answer.** The Files view reads
  `/api/tree?path=<folder>`, so membership and order stay with the route, and refetches
  on an intersecting change, as `folderContext` does.
- **Merging.** An object arrives from several feeds, and the table keeps one record per
  identity. A summary is replaced by a newer generation of the feed that supplied it, or
  by another feed’s summary with a strictly later `updated_at`, which is
  `withListedState`’s rule.
  An unknown time is older than any known one, so across feeds a summary with a time
  replaces one without, and a summary without a time never replaces another feed’s.
- **Facets are keyed, not aged.** A facet carries the revision it describes, a pull
  request’s `changes` its head and base, and is replaced whole by another facet for the
  same key. A facet for a key the summary no longer shows is not drawn and is not an
  error: it is about another revision, and it stays in the lane’s bounded memory for a
  return to that revision.
  This is the rule `briefMatches` keeps today (`github/pull-summary-brief.js:67`).
- **A facet may keep its own lane.** `ensure` asks the type’s loader, and a loader may
  be an existing batched route and memory.
  The pull request’s `changes` loader is the `pull-files-summary` lane and
  `documentRowLines` that the Pulls rows and the page already share; the store does not
  hold a second copy.
- **Freshness.** Each source keeps the mechanism it has, tabulated below, and a
  collection handle reports one vocabulary over them: absent, pending, current, or
  stale, and whether a refresh is running.
- **One name for a counter.** `generation` names every counter that moves when a thing
  changes: a feed’s, a collection’s, a facet loader’s, and a view state’s. “Revision”
  stays a commit, as [Open Modes](../../architecture/arch-open-modes.md) uses it, so a
  facet keyed by revision is keyed by commits and not by a counter.
- **Subscriptions.** Per object and per collection, as `directoryTotals.subscribe` and
  `folderContext.subscribe` work now.
  A view never subscribes; the list host and the page do, and repaint through `update`.

| Type | Freshness mechanism it keeps |
| --- | --- |
| File, folder | Pushed by the event stream within its scope; refetched on an intersecting change beyond it; fixed on a pin |
| Commit | Immutable; its `refs` facet moves with the history generation |
| Pull request | The catalog’s content generation, entity tags, and polling |

**The pull request collection in Phase 1.** The Pulls panel’s controller stays the one
reader and writer of the list, and five things about it change
([Decision 14](#decision-14-who-reads-a-collection)):

1. It holds objects and describes at paint, where it now holds descriptions, and it
   compares objects, so a change only the wide row shows still repaints.
2. It registers its held lists as the collection with `registerCollection`, and puts
   each object in the store with `put`.
3. It counts a mounted pane list as shown, where `live()` now asks only about the tab
   (`github/pulls-panel.js:921`), so the wide list does not freeze when the reader
   switches the navigation to Files.
4. Either list’s request for more drives its paging, within `DISPLAY_ROWS`.
5. The change-line lane wants the lines of the rows any shown list draws.
   Today `rowLines.want` is passed nothing whenever the panel is hidden
   (`github/pulls-panel.js:4541-4547`), and the lane is created in the panel’s mount
   (`:5028`), so it moves to where the collection lives.

Its generations, entity tags, offers, cores, and prefetch are untouched.
Because this changes what an existing surface reads, it lands behind a measured pair on
the Pulls tab, as rule 5 requires.

### The View Model

The object model says what each thing is.
The view model says what a viewer shows: which object, in which page view, beside which
list, with which rows current and open.
An agent reads it to learn what the reader is looking at, and writes to it to show the
reader something.

[View Model and View State](plan-2026-11-18-view-model-and-view-state.md) holds that
design: the view state each viewer publishes, the `present` intent, the `metabrowser.ui`
contracts, Phase 4, and Decisions VM-1 to VM-10. It adds no vocabulary where this plan
has one, and uses these as defined here:

- the reference and the collection reference ([Approach](#approach)), which name what a
  view state shows;
- the shape names ([Shapes](#shapes)), and a summary with facets
  ([Summary and Facets](#summary-and-facets));
- the list host’s state record, which is a view state’s list facet
  ([The List Host](#the-list-host));
- the collection convention ([Decision 3](#decision-3-the-collection-envelope)), in
  which the list of viewers answers;
- the type tokens of [Decision 5](#decision-5-identity), which an intent may name;
- `--show`’s `object:` line ([Routes and the CLI](#routes-and-the-cli)), which a view
  state’s `object` must equal.

### Routes and the CLI

Objects are served by the layer that owns them, through routes that mostly exist:

| Route | Serves | Change |
| --- | --- | --- |
| `GET /api/object-types` | The registry: each type’s contract and schema digest, its views by shape, its collections, its page kind, and the route a reference to it leads to | New, core |
| `GET /api/contracts`, `GET /api/contract` | Every contract a build registers, with its digest, and one compiled schema, so an agent reads a schema through `--api` | New, core; specified by the agent interface plan’s [Self-Description](plan-2026-11-18-agent-interface.md#self-description) |
| `GET /api/plugin/github/pulls` | The pull request collection; `rows` are `PullRequest` summaries | Rows conform, Phase 1 |
| `POST /api/plugin/github/pulls-refresh` | A refresh; its answer nests the `pulls` list envelope, with no rows | Conforms with `pulls`, Phase 1 |
| `GET /api/plugin/github/pull` | One pull request with its facets | Phase 3 |
| `GET /api/plugin/github/pull-files-summary` | The `changes` facet of up to `MAX_SUMMARY_NUMBERS` pull requests, from the cache | None; it becomes the facet’s loader |
| `GET /api/plugin/github/stack-change` | A stack’s change totals | None until a stack is a type |
| `GET /api/tree`, `/api/recent` | Files and folders, in their compact encodings, read through adapters | None here. The Recent tab plan’s [RT-6](plan-2026-11-18-recent-tab-updates-and-events.md#rt-6-the-name) renames this `/api/recent` to `/api/recent-files` |
| `GET /api/file?path=<id>` | The file or folder envelope, which is where a `file` or `folder` reference leads | None |
| `GET /api/git/log`, `/api/git/commit/<rev>` | Commits; the log row is close to the summary already | Rows conform, Phase 2 |
| The Recent tab’s routes | The mixed collection, one of its items, and the working-tree changes object | New, core; named and built by the Recent tab plan ([Routes, the CLI, and the View Model](plan-2026-11-18-recent-tab-updates-and-events.md#routes-the-cli-and-the-view-model)) |

- **A plugin’s object routes are ordinary `[[data_hook]]` routes,** which `--api`
  reaches by construction.
- **No route answers a `File` or `Folder` object.** The tree and Recent stay compact,
  and the adapters that make objects of their rows run in the browser.
  A reference to a file or a folder therefore leads to `/api/file?path=<id>`, which
  answers the envelope for either (`server.py:3350`, `:3375`), and the registry names
  that route for both types, as it names every type’s
  ([Decision 15](#decision-15-routes)).
- **The registry route builds no validator.** It answers from the manifests and each
  packaged schema’s recorded digest.
- **The `pulls` route answers two shapes.** Its list answer follows the collection
  convention. Its search answer (`q=`) keeps its own rows until Quick Search adopts
  references in Phase 3. Both say `rows`, so validation applies to the list answer, the
  one a `q` parameter does not select.
- **`pulls-refresh` carries the same envelope.** Its answer nests what `list_envelope`
  builds for `pulls` from `read_catalog_window`, asked for no rows
  (`github/sidekick.py:689`, `github/pull_list_route.py:279`), so it changes in the
  commit that changes `pulls`, with its golden
  (`tests/golden/cli-github-pulls-refresh.txt:41-63`) and the parity rows that name it:
  `github.pulls-panel`, `github.pulls-watch`, and `github.background-freshness`
  ([Parity Registry](../../architecture/arch-parity-registry.md)).

`metab` exposes the model three ways:

- **`--api`** issues each route and validates the objects it answers, so its goldens are
  contract evidence.
- **`--show`** adds two lines to a selection’s report: `object:` with the type and
  contract of what the address selects, and `shapes:` with the shapes that type has
  views for. `--show /pulls`, which asks the route for no rows, reports the collection
  and its member type from the registry.
  The `object:`, `kind:`, and `views:` lines are a view state’s `object`, `pane.kind`,
  and `pane.views` for the same address, under the same names, and one agreement test
  holds the two together
  ([Parity for the View Model](plan-2026-11-18-view-model-and-view-state.md#parity-for-the-view-model)).
  Once [Decision 5](#decision-5-identity)’s rename lands, the `object:` type is also the
  token `--present --format json` prints as `kind` for the same target.
  Until then `--present` says `tree` for a folder on GitHub and `repository` for a
  repository’s root, where the type is `folder`, as the table under
  [Types, Identity, and the Header](#types-identity-and-the-header) maps them.
- **`devtools/check_parity.py`** gains two rules beside the kind rule.
  Every registered type with a page of its own appears as an exact `object: <type>` line
  in a successful `--show` golden; a type addressed inside its parent’s page, which
  `--show` reports as the parent, appears instead as a validated row in a collection
  route’s `--api` golden.
  Every registered view of a type in a row shape has an interaction row whose session
  ran its named `describe` function.
  A page view has a `render` and no `describe`, so this rule does not count it.
  They sit beside the `owned-model` data rows `devtools/check_parity.py` gained with
  #540 (`devtools/check_parity.py:56-64`), which are the precedent for a rule over
  models.

### Plugins

A plugin declares a type as it declares a kind and a view, in its manifest, and
registers the drawing in JavaScript:

```toml
[[object_type]]
id = "pull-request"
contract = "metabrowser.github:PullRequest/v1"
model = "metabrowser.builtin_plugins.github.objects:PullRequestObject"
schema = "pull-request-v1.schema.yaml"
corpus = "pull-request-conformance.json"
page_kind = "pull-request"
facets = ["description", "merge", "stack", "checks", "changes"]

[[object_view]]
type = "pull-request"
shape = "wide-row"
facets = ["stack"]

[[collection]]
name = "pulls"
members = ["pull-request"]
route = "pulls"
```

A collection’s key is `name`, the `name` of a collection reference and of
`registerCollection`. A type’s key is `id`, as a kind’s and a view’s are.
The manifest declares every structure, a type’s facets and a view’s among them, and
JavaScript supplies functions only (Decision PS-1).

- **Validation at load.** The loader refuses a type another plugin declares, a view for
  a shape the host does not define, a collection naming a route the plugin does not
  declare, and a contract identifier outside the registry’s grammar.
- **The model is not imported at load.** A sidekick is imported at startup, and the
  GitHub sidekick imports nothing from the cache for that reason
  (`github/sidekick.py:13`). The loader records `model` as text, and only the drift
  check reads it, for a plugin whose Python runs in the server.
- **The packaged schema is the authority, for every plugin.** #380 proposes running a
  third-party plugin’s Python in a worker on its own environment, where the host cannot
  import its model. Validating such a plugin by its schema and an in-process plugin by
  its model would be two validation paths for one kind of declaration.
  So validation reads the compiled `schema` each plugin packages, by the plugin
  authoring plan’s
  [Decision PS-7](plan-2026-11-18-plugin-authoring-objects-views.md#decision-ps-7-one-validation-path),
  and `model` serves the drift check alone.
- **A view for someone else’s type.** A plugin may register a view for a type it does
  not own, as it may add a tab to another plugin’s kind.
- **Two views of one type in one shape.** A later `[[object_view]]` for the same type
  and shape, in discovery order, replaces the earlier one, as a later `[[view]]` with
  the same id does, and `metab --doctor` names the plugins on both sides
  ([Manifests](../../architecture/arch-plugin-system.md#manifests)). The browser keeps
  the winner’s `registerView` and ignores the loser’s, by checking each registration
  against the manifests’ declarations, as the plugin authoring plan’s
  [JavaScript SDK](plan-2026-11-18-plugin-authoring-objects-views.md#javascript-sdk)
  section sets out under Lifecycle.
- **Python is required for a type, not for a view.** An operator-directory plugin runs
  no Python, so it can draw existing types and cannot serve a new one.
  Under #380 that Python is a worker’s, and a `[[collection_source]]` becomes a worker
  hook with a deadline.
- **A test binds the two halves.** As `tests/test_plugin_e2e_render.py` fails a manifest
  view with no `registerView`, it fails an `[[object_view]]` with no
  `mb.objects.registerView`.
- **Later:** a `[[collection_source]]`, by which a plugin’s source joins the Recent
  tab’s list, in that plan’s R3. The block names a data-hook route, by the plugin
  authoring plan’s
  [Decision PS-3](plan-2026-11-18-plugin-authoring-objects-views.md#decision-ps-3-what-a-collection-source-names).

This moves pull requests toward the plugin without a new registration surface for panels
or routes. The Pulls tab stays on the internal shell seam, and a container’s children
hook is unchanged. Once a navigation panel is a collection drawn as `nav-row`s, a plugin
panel is a small step, and it is not part of this plan.

[Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md)
specifies this surface key by key and call by call.
Its decisions, PS-1 to PS-7, were taken on 2026-11-18, each at A, and this section is
written to them. Beyond PS-3 and PS-7 above, three shape it:

- **PS-1** puts a view’s `facets`, a type’s facets, and a page’s parts in the manifest,
  where the server, `--doctor`, and the parity check can read them.
- **PS-2** has the store read a declared route by the collection convention, with no
  JavaScript, so `registerCollection` and a type’s `load` are for a controller of the
  plugin’s own, as the Pulls panel’s is.
- **PS-6** indexes a plugin’s assets by type as well as kind, so `mountList` loads the
  plugins that declare or draw its collection’s members before first paint.
  A plugin’s code loads by kind today, so a list drawn outside its type’s own page would
  otherwise select none of them.

That plan also keeps as an open question that `mb.registerView` and
`mb.objects.registerView` share a name and take different arguments.

### Performance

- **No request for a second view.** The wide list of pull requests draws from the
  collection the Pulls tab holds, so `/pulls` paints from memory when the tab has read
  it.
- **Bounded rows.** Windowed lists mount the viewport and an overscan.
  The `/recent` page of cards may instead use `content-visibility` with an intrinsic
  size, which keeps find-in-page; the measurement chooses, as
  [the strategy ladder](../../../large-content-rendering.md#the-strategy-ladder) asks.
- **Nothing per file at scale.** File objects are views over entries already held.
  The Files tree, the catalog, and their feeds are untouched.
- **Prefetch.** A pull request’s `changes` facet is already batched for the rows in view
  (`pull-files-summary`, from the cache alone), and a page opened from a row reads the
  same memory and asks for nothing.
  A wide row reads that lane; a new facet takes the same form, a batch for the rows in
  view and a memory per document, or rides the batch `pull-cores-prepare` uses.
  A hover warms the page as the tree and the Pulls panel do.
- **Loading tiers.** Each module’s tier follows from what first needs it, and neither
  enters the eager path that `devtools/check_startup_scripts.py` bounds:
  - **The store** (`static/object-store.js`) is in the `sdk-views` on-demand bundle,
    beside `registerView`. Its first writer is the Pulls panel, plugin code that already
    waits on that bundle, and `pulls-nav`, which the shell loads whenever it serves a
    GitHub repository (`server.py:1683`), mounts the panel in idle time
    (`static/pulls-nav.js:365-371`). A bundle of its own would be fetched in nearly
    every such session anyway.
    Its bytes are measured against that bundle, which records its own measured size
    (`static/plugin-sdk-views.js:25`).
  - **The list host** (`static/object-list.js`) is an on-demand bundle, loaded at the
    first `mountList` and prefetched in idle time once the Pulls panel mounts, so a
    `/pulls` reached from the tab paints from memory with no fetch.
    A cold load at `/pulls` waits on the fetch, and the `/pulls` first-paint round
    counts it.
  - **A plugin’s views** register with its code.
    A pull request’s address loads the GitHub plugin for first paint, so registering its
    views there is measured against that budget.
- **Lazy mounting.** A folder’s Files view is a nondefault tab, so it mounts on first
  activation, as every hidden view does.
- **No validation on the request path.** A server validates no response.

### What Stays As It Is

- The four layers for a selection: address, kind, model, view.
  An object’s page *is* its kind’s page views.
- The `/api/file` envelope, the tree and catalog encodings, and the event stream.
- The Git graph’s layout, session cursors, and checkpoints.
- The pull-request record, catalog, cores, and their cache formats.
- The Pulls panel’s rows, window, keys, and changed-files trees, until Phase 3.
- The change-line lanes (`github/row-lines.js`, `github/stack-lines.js`,
  `github/pull-summary-brief.js`) and their routes, which the model reads as facet
  loaders.
- The page header and `actorIdentity`, which the model’s `page` shape and `actor`
  sub-object adopt.
- File Diff Format, File Rollup Format, and the cache’s record contracts.
- The URL grammar. No route is added to the browser’s address spaces in Phase 1.

## Key Decisions

Each decision gives the phase that needs it settled, the options it weighed, their
trade-offs, and the decision.
The owner took all of them on 2026-11-18, and this table gathers them.

| Standing, as of 2026-11-18 | Decisions |
| --- | --- |
| Taken by the owner on 2026-11-18 | **1** A, with VM-8: SoftSchema contracts for objects and for UI state. **2** A: internal, described contracts. **3** A: a convention on the internal envelope. **4** A: two registries and one rule. **5** A: `type` and `id`, with `pull-request` and one vocabulary of types everywhere. **6** A: one contract, a summary and whole facets. **7** A: a literal shared header. **8** A: UTC strings at second precision. **9** A: core owns files, folders, and commits, and the GitHub plugin pull requests. **10** A: the contract carries Metabrowser’s meaning. **11** A: a closed set of shapes, with the `card` frame built at its first real use. **12** C: the host frame, with the header through an SDK frame that mb-7t5s builds. **13** A: one store interface, a source per type. **14** A: a collection’s one reader runs while any list of it is shown. **15** A: the owning layer’s routes. **16** A: validation in tests, goldens, and at trust boundaries. **17** A: a page is a page view that mounts list hosts. **18** A: a mixed list is composed on the server. **19** C: a main tab named Recent, designed in the Recent tab plan. **20** A: no SDK bump for an addition, and #380’s versioning rule if #380 is accepted. **21** A: arrows move focus, and Enter opens. **22** D: the page first, the contract half second. **23** A: convergence is decided after Phase 2 |
| Open | None in this plan. The companion plans’ decisions were taken the same day: VM-1 to VM-10, PS-1 to PS-7, RT-1 to RT-7, AI-1 to AI-6, and the implementation map’s Ordering 2. Finding a server the agent did not start is the [host mode plan](plan-2026-11-18-host-mode.md)’s [HM-1](plan-2026-11-18-host-mode.md#decision-hm-1-when-discovery-lands), open there |

Decisions 24 to 33 are VM-1 to VM-10 in
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md#key-decisions),
which maps each old number to its new one.

Phase 1 needs every decision here except 18, 19, and 23, and needs 9 and 17 only in
part. By [Decision 22](#decision-22-the-first-slice) D, what Decisions 1 and 2 govern is
built in Phase 2, and 15, 16, and 20 bear on Phase 1 only in part.

The two plans each have a first step, and name them.
The **object slice** is Phase 1’s, chosen in
[Decision 22](#decision-22-the-first-slice), and the **view slice** is Phase 4’s, chosen
in
[Decision VM-10](plan-2026-11-18-view-model-and-view-state.md#decision-vm-10-the-view-models-first-slice).
Neither needs the other’s code.
What the view slice needs of the object half is a set of definitions and decisions,
listed under
[Phase 4](plan-2026-11-18-view-model-and-view-state.md#phase-4-the-view-model), and
Decision VM-10 sets the order of the two: the view slice first, or beside the object
slice.

### Decision 1: What Describes an Object

**Needed for:** Phase 2, where Decision 22 D builds the contract half.

- **A. A SoftSchema contract per type.** A Pydantic model, a compiled schema, a corpus,
  and an entry in the registry that exists, with its corpus runner and wheel check.
  It costs models for the three core types.
- **B. A Pydantic model, a committed JSON Schema, and a corpus, without SoftSchema,** as
  File Diff Format has.
  No new use of SoftSchema.
  It rebuilds the identifier, the digest, the drift check, and the inventory for a
  second family of contracts.
- **C. JSON Schema generated from the `TypedDict`s,** as the envelope plan proposed.
  Cheap for Git. It yields almost nothing for the tree, by that plan’s own finding, and
  gives no corpus and nothing a plugin can declare.
- **D. Static types and tests only.** Today’s state.
  Nothing a plugin or the CLI can name.

**Decided 2026-11-18: A.** The owner chose a SoftSchema contract per type, and the same
form for the view model’s contracts under
[Decision VM-8](plan-2026-11-18-view-model-and-view-state.md#decision-vm-8-the-schema-form),
so both families take one form.
What follows is the record of what was weighed: the registry machinery A reuses, and its
weak points, which the decision accepts as costs.

What A buys over B is the machinery that exists: the registry builder with its
identifier grammar and digest check (`plugin_loader/artifact_contracts.py:352`), the
corpus runner and round trip in `plugin_loader/artifact_inventory.py`, and the inventory
check in `devtools/check_artifact_contracts.py`, which B would rebuild for a second
family. That is a narrower case than “one registry for every contract.”
SoftSchema supplies a schema’s identity, its canonical digest, and the enforcement check
(`plugin_loader/artifact_contracts.py:255`, `:220`, `:295`). Record validation is
Metabrowser’s own, a JSON Schema pass and then the Pydantic model (`:434-450`). It runs
in the tests, the corpus, and the CLI, and never on a running server, which validates no
response ([Decision 16](#decision-16-runtime-validation)) and checks what a client sends
it with the Pydantic model alone
([UI Contracts](plan-2026-11-18-view-model-and-view-state.md#ui-contracts)). Each family
builds its registry from its own specs, as the cache does
(`cache/contracts.py:232-235`).

The weak points:

- **An object is not a durable record.** The envelope plan kept SoftSchema for records
  written now and read by a later release; one artifact serves and reads an object.
- **There is no YAML stage.** SoftSchema’s guide says to skip it where the workflow has
  no YAML artifact stage and gains nothing from one, and it defines no JSON artifact
  profile (`softschema-guide.md`, “When to Use It” and “Artifact Profiles”, in the
  `softschema` release that `pyproject.toml` pins).
  Objects travel as JSON. The one candidate stage is the CLI printing an object as an
  artifact through `--api --format yaml` with a `softschema:` header, which is an
  [open question](#open-questions); until it is settled, A’s case for objects rests on
  the machinery and on one form for both families.
- **The GitHub records are already closed.** The guide also advises against adoption
  where a closed schema is known and a validator covers each boundary, which is true of
  the GitHub records.
- **It brings no maturity ladder.** The registry rejects every status but `enforced`
  (`plugin_loader/artifact_contracts.py:399-400`) and writes only `enforced` (`:499`).
  Admitting `permissive` for a type still settling is a separate change, listed under
  Open Questions.

With A decided, the envelope plan’s scope narrows to the transport around objects, and
that plan should say so.

The view model’s family was decided with this one
([Decision VM-8](plan-2026-11-18-view-model-and-view-state.md#decision-vm-8-the-schema-form)).
An intent is an artifact another program writes, and a view state is one an agent reads
and a shell may save, so that family has the YAML stage and the durability the first two
weak points say objects lack.
That does not carry over to objects by itself: an intent crosses a program boundary, and
an object does not. What the view model adds for objects is one argument.
Objects enter those artifacts by reference, and an agent that follows a reference would
get the same form if the CLI printed an object as an artifact.
Whether it should stays an open question, which the decision does not wait on, and the
first two weak points stand for objects as accepted costs.

### Decision 2: Standing of the Contracts

**Needed for:** Phase 2, where Decision 22 D builds the contract half; the view slice,
for the `metabrowser.ui` family.

- **A. Internal and described.** Versioned, packaged, corpus-checked, and free to change
  with the artifact. No promise to outside consumers.
- **B. Tool-neutral formats,** as File Diff Format is: a normative document, nothing
  that names Metabrowser, and evolution rules.
  It suits a format another tool writes; a pull request object shaped by one provider’s
  API is not that yet.

**Decided 2026-11-18: A,** revisited at the trigger the compatibility table already
names: a first external plugin author who reads them.

**The `metabrowser.ui` family.** A was written for objects, which one artifact serves
and reads. An intent is written by another program, an agent or a script, so “no promise
to outside consumers” needs its own statement there.
Under A the family is still free to change with a release.
What an outside writer gets in place of a promise is a named contract it can read, an
identifier whose version changes on a break, and a refusal, `invalid`, for an intent
written to another version.
`metab` of the serving release is the writer the project supports.
B’s trigger for this family is the first writer that ships apart from `metab`.

### Decision 3: The Collection Envelope

**Needed for:** Phase 1; the view slice, whose list of viewers answers in the
convention.

- **A. A convention on the internal envelope:** `rows`, `next_after`, `complete`,
  `truncated`, and `generation`, checked by tests, with the rest of the envelope the
  route’s own. It keeps the envelope plan’s decision.
  The keys are the spellings routes already answer: `pulls` says `rows` and `next_after`
  (`github/pull_list_route.py:97`, `:306`), `pull-files` and the search answer say
  `rows` (`github/pull_files_route.py:549`, `github/pull_catalog.py:648`), and the cache
  routes say `next_after` (`cache/wire.py:202`). So the pull request list keeps its
  keys, and the Git log is the main rename: its `commits` and `cursor`
  (`git/wire.py:207-208`) become `rows` and `next_after`, and its `cursor` parameter
  becomes `after`. A cursor is opaque to the store, a number for pull requests and a
  string for the cache, and is passed back as `after`. `generation` is the one name for
  a counter that moves when a thing changes: a collection’s here, a facet loader’s, and
  a view state’s. “Revision” stays a commit, as Open Modes uses it.
- **B. A `Collection` contract** wrapping the rows.
  Uniform and validated.
  It makes every list route’s freshness, counts, and cursors part of a versioned
  contract, which is what that plan declined.

**Decided 2026-11-18: A.** One cost of these spellings: `rows` names a drawing, and the
`/recent` page draws its members as cards.
One spelling for one fact, which
[the Background](#where-the-same-fact-is-spelled-differently) counts against today’s
wires, outweighs it; `items` and `next` would add a third spelling of each key.

The Git log’s rename has a cost to settle when it is made.
The golden normalizer rewrites the log’s top-level `cursor`, because it carries a
per-request session token no fixture can pin (`normalize.py:32-43`), while the pull
request goldens pin `next_after` as a number
(`tests/golden/cli-github-pulls.tryscript.md:84`). After the rename one key holds both,
so the normalizer must tell a session token from a stable cursor by more than its place
in the envelope.

### Decision 4: Types and Kinds

**Needed for:** Phase 1.

- **A. Two registries and one rule.** A type owns the summary shapes; a kind owns the
  page. Kinds and classification are unchanged.
- **B. One registry.** Every type is a kind, and a row is a `[[view]]` with a shape.
  A Markdown file’s row would then need kinds to inherit from `file`, and a tab and a
  row would share one concept.
- **C. Types replace kinds,** with the format as a field.
  It rewrites classification for no gain to these surfaces.

**Decided 2026-11-18: A.**

### Decision 5: Identity

**Needed for:** Phase 1; the view slice, for the type names and identifiers a reference
holds.

- **A. `type` and `id`, with `href` derived.** The identifiers are the keys the stores
  use today. It serves nested objects, which have no page of their own, and whose
  reference names the parent.
- **B. The address is the identity.** One concept, and `--show` already takes addresses.
  A comment or a check run has no address of its own, and a path’s address does not say
  whether it is a file or a folder.
- **C. Opaque global identifiers,** as GraphQL nodes have.
  They need a resolver and are unreadable in a golden.

**Decided 2026-11-18: A, with one vocabulary of types everywhere.** The owner chose
`type` and `id` with `href` derived, and chose the type tokens `file`, `folder`,
`commit`, and `pull-request` for every place that names what a target is.
#534’s “addresses first” agrees with A: an address is derived from the identity and is
what a user, the CLI, and the app hand over.

The spelling is `pull-request`, not `pull_request`. It is the page kind’s id
(`github/manifest.toml:149-150`) and the form of every id in the built-in manifests, so
a view state says `object.type: pull-request` beside `pane.kind: pull-request`, and a
manifest block `id = "pull-request"` beside `page_kind = "pull-request"`.

The decision changes two vocabularies on `main`, which divide targets differently from
the types and from each other (`cli/present.py:126-128`, `cache/urls.py:77`):

- **`--present`’s `kind` and `SelectionKind` take the type tokens.** `repository` and
  `tree` become `folder`, `blob` becomes `file`, and `pull_request` becomes
  `pull-request`, as the table under
  [Types, Identity, and the Header](#types-identity-and-the-header) maps them.
- **The rename is one commit, with the macOS app.** The app reads `kind`
  (`apps/macos/Sources/ShellCore/Folders/PresentPlan.swift:76-82`), and
  [AGENTS.md](../../../../AGENTS.md#compatibility-and-legacy-code) requires that what
  the app uses of `metab` change with the app in the same commit, and that
  `MetabRequirement.minimumRelease` rise with it
  (`apps/macos/Sources/ShellCore/Setup/MetabVersion.swift:56`).
- **A separate field keeps a repository’s root apart from a named tree.** With both
  spelled `folder`, the kind no longer says whether a ref was named, and three readers
  tell the two apart by the kind today.
  A bare repository URL prints no selection lines (`cli/selection.py:262`). It opens the
  default revision, with no pin resolved from the URL (`cli/git_pin_cli.py:198`). And it
  resolves to the default branch, where a tree or a blob resolves the ref and path it
  names (`cache/resolve.py:754`). So the selection and `--present`’s report carry “the
  repository’s root, no ref named” in a field of their own, and those readers move to
  that field in the rename’s commit.

### Decision 6: Summary and Detail

**Needed for:** Phase 1.

- **A. One contract: a required summary and optional, all-or-nothing facets.** A partial
  object is valid, the store merges by facet, and a view states what it uses.
- **B. Two contracts per type,** `Summary` and `Detail`. Simple to state.
  It fixes two levels where pull requests already have three (row, core, record), and
  duplicates the summary’s fields.
- **C. One contract with every detail field optional.** The loosest: a view cannot tell
  “not loaded” from “absent.”

**Decided 2026-11-18: A.**

### Decision 7: The Shared Header

**Needed for:** Phase 1.

- **A. Literal fields:** `type`, `id`, `href`, `title`, `updated_at`, and an optional
  `actor`. An object is self-describing: the CLI, an agent, and the fallback view can
  list, order, and label any type without the registry.
  A commit’s `title` is its subject and a file’s is its name, which reads slightly
  oddly.
- **B. Roles, not fields.** Only `type` and `id` are shared; the registry says which of
  a type’s own fields is its title and its time.
  Natural names, and a generic reader needs the registry.
- **C. A presentation header,** with a subtitle, icon, and badges, as VS Code’s tree
  item has. The host could draw every row with no type code.
  It puts drawing decisions in the data and cannot express a graph gutter or a stack
  badge.

**Decided 2026-11-18: A,** with C’s drawing kept where it now lives, in a view.
#487 and #550 have built the presentation header as a drawing, not as data:
`MetabrowserViewHeaderParts{path, eyebrow, iconHtml, title, line}` (#550, in
`static/types.d.ts` on `main` since it merged) is what a page’s header `describe`
returns, filled from the object’s `title`, `actor`, and `updated_at`. So the object
stays self-describing, and the header every page shows is one view of that header.

### Decision 8: Timestamps

**Needed for:** Phase 1.

- **A. A UTC string at second precision,** the form the GitHub models already use
  (`github/pull_record.py:108`). It is fixed width, so the string comparison
  `withListedState` makes keeps working; it reads plainly in a golden and to an agent;
  and it cannot be mistaken for milliseconds or nanoseconds.
  A file’s time loses its fraction, every age computation parses it, and the Git log’s
  times and their readers in `static/git-panel.js` change in Phase 2.
- **B. Epoch seconds as a number,** the convention `git/wire.py` states for the tree and
  Git wires, and what the formatters take.
  No parsing, numeric comparison, sub-second order, and no change to Git.
  A schema can say only “number,” the unit lives in a naming rule, and the pull request
  projection and its browser readers convert in Phase 1.

**Decided 2026-11-18: A,** a UTC string at second precision.
Its costs are the ones listed under A, and one more since #550, which added `mtime` to
`/api/file` in epoch seconds: the file projection converts that field too.
Two forms were ruled out.
The cache’s canonical timestamp has optional milliseconds (`cache/records.py:58`), so
its strings are not comparable.
A nanosecond integer exceeds the safe-integer range SoftSchema’s portable values allow.

### Decision 9: Who Owns Each Type

**Needed for:** Phase 1 for pull requests; Phase 2 for files, folders, and commits; for
comments, whenever one becomes a type ([Extension Path](#extension-path)).

- **A. Core owns files, folders, and commits; the GitHub plugin owns pull requests and
  comments.** A contract, its projection, and its views sit with the records they come
  from. File and folder views live in the built-in `folder` plugin, and commit views in
  the shell beside the Git panel, because Git is core today.
- **B. A provider-neutral pull request in core.** It prepares for another host, which
  nothing plans, and would be designed against one example.
- **C. Move Git into a built-in plugin first,** so every view is a plugin’s. Consistent,
  and a large move this plan does not need.

**Decided 2026-11-18: A.** Under A, core also owns the three types the Recent tab plan
adds, `update`, `event`, and `working-tree-changes`
([Contracts](plan-2026-11-18-recent-tab-updates-and-events.md#contracts)).

### Decision 10: How Far a Contract Normalizes Its Source

**Needed for:** Phase 1.

- **A. The contract carries Metabrowser’s meaning:** one four-valued `state` for a pull
  request, derived in the projection.
  Each reader drops its derivation as it adopts the object: the list in Phase 1; the
  page, search, and `--show` in Phase 3.
- **B. The contract mirrors the provider:** GitHub’s `state`, `draft`, and `merged`,
  with the derivation shared in one helper per language.
  The object stays recognizable beside GitHub’s API, and the derivation still exists
  twice.

**Decided 2026-11-18: A.**

### Decision 11: The Set of Shapes

**Needed for:** Phase 1.

- **A. A closed set the host owns:** `nav-row`, `wide-row`, `card`, and `page`. Each is
  a contract with the list host about height, activation, and slots, and the design
  system documents each once.
- **B. Plugin-defined shapes.** A plugin could invent a board or a gallery.
  Nothing else could draw that shape for other types, so a mixed list would fall back
  for most of its items.

**Decided 2026-11-18: A,** adding a shape to the host when a second type needs it.
`card` stays in the named set, and its frame is built only with its first real use: the
`/recent` page in the Recent tab plan’s
[R4](plan-2026-11-18-recent-tab-updates-and-events.md#r4-later-each-alone), or the
implementation map’s
[C5](plan-2026-11-18-object-model-implementation-map.md#stacks-c-r-and-x). Until then no
code draws a card, and nothing reserves a frame for one.
A shape’s frame is written to the most demanding row that uses it, so `nav-row` admits a
facet line as its one child, as the Pulls row has since #491 ([Shapes](#shapes)).

### Decision 12: How a View Is Defined

**Needed for:** Phase 1.

- **A. A painter per type and shape,** with no host frame.
  The most freedom; every view restates the link, the roles, and the row tokens, which
  is today’s drift.
- **B. A description the host paints.** Uniform rows and no DOM code in a type.
  It needs a vocabulary rich enough for a graph, ref chips, and a stack badge before one
  row ships.
- **C. A host frame, a pure `describe`, a type’s `paint` inside the frame, and a header
  fallback.** Shared slot primitives are extracted as they repeat.

**Decided 2026-11-18: C, with the page header drawn through an SDK frame that bead
mb-7t5s builds.** Three slot primitives have been extracted already: `actorIdentity`,
`changeLine`, and the view header.
The header is shared by class structure today: #550’s review decided that another kind
writes the `.view-header-*` classes itself rather than calling its builder.
Under C the host owns the frame, so bead mb-7t5s, which moves the pull request and
commit pages onto the view header, takes the header through an SDK frame, not through
the classes, which Phase 3 would otherwise undo.
So mb-7t5s lands before any page this plan draws under the header.

### Decision 13: The Browser Store

**Needed for:** Phase 1.

- **A. One interface, a source per type.** Files and folders wrap the stores that exist;
  other types use a default table.
- **B. One normalized table for every type.** The simplest to describe.
  It would copy a large tree’s entries, or need special cases that amount to A.
- **C. Today’s stores, with conventions.** No new code, and every new surface writes its
  own, as now.

**Decided 2026-11-18: A.**

### Decision 14: Who Reads a Collection

**Needed for:** Phase 1.

The Pulls panel’s controller reads only while its tab is shown, and is private to the
panel.

- **A. The collection’s one reader runs while any list of it is shown.** The pane’s list
  stays live when the reader switches the navigation to Files.
  It needs the five controller changes under [Browser Data Model](#browser-data-model),
  the fifth for the change lines.
- **B. The pane’s list mirrors the panel.** The smallest change.
  A visible list stops refreshing whenever the tab is hidden.
- **C. A second controller for the pane.** No change to the panel.
  Two readers poll one route and can hold two generations of one list.

**Decided 2026-11-18: A.** The Recent tab counts as a shown list of `pulls` too, so the
catalog refreshes while Recent is in front, in that plan’s R3.

### Decision 15: Routes

**Needed for:** Phase 1; by Decision 22 D, the registry route waits for Phase 2.

- **A. The owning layer’s routes.** A registry entry names each collection’s route, and
  each type’s object route, the one a reference to that type leads to; existing routes
  conform when their surface adopts the model.
  Core adds only the registry route and the mixed collection.
- **B. A generic dispatcher,** `/api/objects/<type>/<id>` and `/api/collections/<name>`,
  calling registered sources.
  Uniform addresses. It adds a Python registration surface and a second route to
  everything that has one.

**Decided 2026-11-18: A.** With each type’s object route in the registry, a reference
found in a view state can be followed without a dispatcher.
For `file` and `folder` that route is `/api/file?path=<id>`, which answers an envelope
and not an object ([Routes and the CLI](#routes-and-the-cli)). Where the view slice
lands before the registry route, it states the same table as a constant
([Reading](plan-2026-11-18-view-model-and-view-state.md#reading)).

### Decision 16: Runtime Validation

**Needed for:** Phase 1; by Decision 22 D, `--api` validation waits for Phase 2 and the
browser’s normalizer does not.

A server already loads the schema libraries on first use of the cache or a GitHub route
(`cache/atomic.py:26`, `:41`, `github/pull_list.py:43`); only startup is gated.
The cost in question is validation time per row.

- **A. Validate in tests, in goldens through `--api`, and where data crosses a trust
  boundary,** which today is the cache’s reads and writes; a strict normalizer in the
  browser. A producer bug that no test or golden reaches is caught by the normalizer, in
  the browser.
- **B. Validate every object a server answers.** The strongest guarantee.
  It adds per-row work to a pull request window, and to the tree and log paths the
  load-time work measured.
- **C. A schema validator in the browser.** It ships a validator to every page for data
  the same artifact produced.

**Decided 2026-11-18: A,** with B open for a route where a measurement shows it is
cheap. The view model adds one trust boundary to A’s list: what a page or an agent sends
to the `/api/ui` routes, which a running server checks with the contract’s Pydantic
model alone ([UI Contracts](plan-2026-11-18-view-model-and-view-state.md#ui-contracts)).

### Decision 17: Composing a Page of Several Lists

**Needed for:** Phase 1 for the `/pulls` page, which mounts one list; Phase 2 for a page
of several.

- **A. A page is an ordinary page view that mounts list hosts,** one or several, in
  code.
- **B. A declared page:** a manifest lists collections and shapes, and the host lays
  them out with no JavaScript.
  Simple pages cost nothing to write.
  It is a layout language to design before a second page exists.
- **C. A collection as a Folder Overview panel,** through the panel registry.
  It fits a summary inside Overview and not a page of its own.

**Decided 2026-11-18: A,** with C a natural later addition for Overview.

### Decision 18: Composing a Mixed List

**Needed for:** Phase 2.

- **A. On the server, from registered sources,** as one route with one cursor.
  Each source needs a new time-ordered read, and the pull request source a catalog
  schema change
  ([Tiers and Sources](plan-2026-11-18-recent-tab-updates-and-events.md#tiers-and-sources)).
- **B. In the browser,** merging each type’s collection.
  No new route. Order and membership would then be browser logic, which the parity rule
  assigns to a route, and the sources would still need time-ordered reads.

**Decided 2026-11-18: A.** The Recent tab plan designs on it, and says which sources the
first version covers and what each one costs.

### Decision 19: Where Recent Changes Lives

**Needed for:** the Recent tab plan’s first phase, R1.

- **A. A page view of the `folder` kind.** Every folder has one, scoped to what changed
  beneath it; the repository’s root adds pull requests and comments.
  No new address space.
  A path-scoped commit walk costs more than the unscoped one.
- **B. A route of its own,** as `/pulls` is: the served source’s changes, unscoped.
  The simplest to build, and a new address space.
- **C. A main navigation tab** beside Files, Commits, and Pulls.
  The most visible, and a timeline of cards is a poor fit for a narrow panel.

**Decided 2026-11-18: C, a main tab named Recent,** designed in
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md).
The tab draws rows, which answers C’s cost.
Option B’s address survives as `/recent`, the tab’s list address and its page of cards.
Option A is dropped, and scoping the list to a folder is an open question in that plan.
The name collides with the Files tab’s Recent view and Open Recent’s targets
([Approach](#approach)), which that plan’s
[RT-6](plan-2026-11-18-recent-tab-updates-and-events.md#rt-6-the-name) settles: the
Files filter keeps its control and gives up the name.

### Decision 20: Plugin Declaration and the SDK Gate

**Needed for:** Phase 1; by Decision 22 D, the manifest blocks wait for Phase 2 and
`mb.objects` does not.
`mb.ui`, by which a page view reports its parts, arrives in a later slice of
[Phase 4](plan-2026-11-18-view-model-and-view-state.md#phase-4-the-view-model) and falls
under the same answer.

- **A. Manifest blocks, `mb.objects`, and later `mb.ui`, with no SDK bump for adding
  them.** The rule in
  [Plugin System](../../architecture/arch-plugin-system.md#the-sdk-version-gate) is that
  an additive SDK method does not change the version
  (`docs/project/architecture/arch-plugin-system.md:81`). This option extends that rule
  to a manifest block, which is not a method: the manifest schema forbids unknown keys
  (`plugin_loader/manifest.py:348`), so an older host refuses a manifest that uses the
  blocks whatever the version says.
  A break in a core contract bumps it.
- **B. The same, with a bump when it lands,** so a plugin that uses the blocks is
  refused by an older host with the version message, not an unknown-key error.
- **C. JavaScript only,** with no manifest blocks.
  Less to validate, and nothing `--doctor`, the CLI, or the parity check can see.

**Decided 2026-11-18: A, and #380’s versioning rule if #380 is accepted.** #380’s
Decision 8 proposes one `sdk_version` under Cargo’s caret rule, where an addition bumps
the patch number, the gate reads the version from the raw manifest before schema
validation, and each change is listed in `sdk-changes.toml`. If that is accepted, this
decision becomes “a patch bump and an `sdk-changes` entry”, and B’s worry, an
unknown-key error on an older host, is gone, because the version is read before the
keys. The plugin authoring plan’s
[Versioning](plan-2026-11-18-plugin-authoring-objects-views.md#versioning) tabulates
both rules for each kind of change.

### Decision 21: Keyboard Contract for a List in the Pane

**Needed for:** Phase 1.

- **A. Arrows and J and K move focus; Enter or a click opens and pushes history.**
- **B. The navigation contract: moving opens.** In the pane it would replace the list
  with the first row the reader moved to.
- **C. Native link order only.** A Tab stop per row in a list of hundreds.

**Decided 2026-11-18: A,** as a new design-system section beside Navigational Row
Collections, with the list host registered in the same check.
A wide row with a facet line under it takes the Pulls tab’s rule for that line: Right
moves to it, and Enter or Space there toggles what it owns.

### Decision 22: The First Slice

**Needed for:** Phase 1, before anything else.

This decision chooses the **object slice**, the object model’s first step.
The view model’s first step, the view slice, is
[Decision VM-10](plan-2026-11-18-view-model-and-view-state.md#decision-vm-10-the-view-models-first-slice)’s,
which also sets the order of the two.

- **A. The pull requests page, on the model.** The wide row shows what the catalog row
  holds: state, title, labels, number, author, opened and updated ages, and both
  branches; the stack position, from the stacks snapshot, as the narrow row does; and
  the change line, from the `changes` facet’s existing lane, as the narrow row does
  since #491. It changes the `pulls` route’s rows and the panel’s controller, behind a
  measured pair.
- **B. The same page inside the plugin, with no shared model.** The fastest route to one
  page. The next surface starts from nothing, and the panel’s store still discards the
  fields the wide row needs.
- **C. The folder’s Files view first.** Core only, no network, and no change to the
  Pulls panel. It exercises neither a plugin type nor a route that answers objects, since
  the tree stays compact.
- **D. The page first, the contract half second.** Phase 1 builds the `PullRequest`
  projection, the store, the list host, the split of `describe` and `paint`, and the
  wide page, as A does.
  The contract registry, the manifest blocks, the registry route, `--api` validation,
  and the two new parity rules wait for Phase 2, when the file, folder, and commit types
  can test the header against more than one type.
  The object slice does not need the registry for parity: the `pulls` route’s `--api`
  goldens and the `github.pulls-panel` interaction row already pin the route and its
  `describe` functions, and `github.pulls-row-lines` pins the change lines
  ([Parity Registry](../../architecture/arch-parity-registry.md)). It ships the page
  sooner and designs the header against four types before the header is a contract.
  Its cost is a second pass over the projection, and over the `pulls` goldens, when the
  contract lands.

**Decided 2026-11-18: D.** A builds the whole contract half for one type its own plugin
owns, and D tests that design against the core types first, for the price of a second
pass over one projection.
The phases below are written for D: the contract, the manifest blocks, and the registry
route with its validation and parity rules are Phase 2 items, and the architecture
document’s contract and declaration tables arrive with them.
Which type the object model reaches first is a separate matter of order.
The [implementation map](plan-2026-11-18-object-model-implementation-map.md#orderings)’s
Ordering 2, decided the same day, puts a checkout’s working-tree changes ahead of the
pull requests page. The object slice reuses what has landed since the plan was first
written: the `changes` facet’s route and memory, the view header for the page,
`actorIdentity` for the author, and the drawn-from-disk fixture for the corpus.
Three things are left out of the object slice on purpose.
Review decision, check status, and comment counts are not in the catalog, whose query is
kept light (`github/pull_list_refresh.py:81`); adding them is a separate change with its
GraphQL cost measured.
No `nav-row` view is registered: the panel keeps drawing its own rows, from the same
objects. The route’s search answer keeps its shape.

### Decision 23: Converging the Existing Surfaces

**Needed for:** Phase 3, after Phase 2.

- **A. Decide after Phase 2.** Phase 3 is listed, and each surface moves only on a
  measured pair showing no regression.
- **B. Commit now** to moving every row builder onto the model.
- **C. Never.** New surfaces use the model, and the old ones stay.

**Decided 2026-11-18: A.** The duplicate builders are a real cost, and the Files tree
and the Git graph are also the most measured code in the shell.
The Pulls row has grown since the plan was first written, to three lines, a facet line
as a second focus stop, and stack sections that read their own data, so moving it is the
largest of the Phase 3 items, and the list host is specified to carry it
([The List Host](#the-list-host)). The list host is specified to make convergence
possible: disclosure rows, activation options, and collection context exist for the
three navigation lists, not for the new pages.

## Implementation Plan

The [implementation map](plan-2026-11-18-object-model-implementation-map.md) divides
these phases into stacks of pull requests, with their order, dependencies, and
measurement gates. Phase 4, the view model, is in
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md#phase-4-the-view-model);
its first step, the view slice, waits for no other phase’s code.
The Recent tab’s phases, R1 to R4, are in
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md#implementation-plan).

One item belongs to no phase.
[Decision 5](#decision-5-identity) makes it, and neither slice needs its code, since the
object types are spelled its way from the start; the implementation map lands it first:

- [ ] Rename `--present`’s `kind` and `SelectionKind` to the type tokens, with the macOS
  app’s reader and its `minimumRelease` in the same commit, and add the field that keeps
  a repository’s root with no ref named apart from a named tree, moving the readers at
  `cli/selection.py:262`, `cli/git_pin_cli.py:198`, and `cache/resolve.py:754` onto it.

### Phase 1: The Model and the Pull Requests Page

Phase 1 is the object slice, as [Decision 22](#decision-22-the-first-slice) D sets it:
the projection, the store, the list host, and the page.
The contract half is in Phase 2.

- [ ] Add the header and the shared sub-objects as Pydantic models in `objects/`, and
  the `PullRequest` model in `github/objects.py`, with no registry and no compiled
  contract yet. The reference and collection reference definitions are among the shared
  ones, unless the view slice has landed them.
- [ ] Project `PullListRow` to the object where the catalog makes its wire rows
  (`github/pull_catalog.py:531`), and change the readers of the `pulls` list answer in
  the same commit. Under [Decision 3](#decision-3-the-collection-envelope) A the envelope
  keeps its keys, so what changes is what each row holds.
  The readers are, in `github/pulls-panel.js`: `isEnvelope` (`:553`), `describeRow`
  (`:312`), `describePulls` (`:430`), `pumpCores` (`:1016`), `holdRows` (`:1587`),
  `holdEnvelope` (`:1610`), `holdContent` (`:1770`), `arrivalsFromTop` (`:1836`), `ask`
  (`:2096`), and `loadWindow` (`:2516`); `noteListed`, which takes the held descriptions
  (`github/pull-state.js:70`); and the readers of the description’s `head`, which the
  change lines are read again by: `pulls-panel.js:4048`, `:4129`, and `:4545`,
  `createRowLines` (`github/row-lines.js:173`), `createStackLines`
  (`github/stack-lines.js:234`), and `github/pull-summary-brief.js`. The `pulls-refresh`
  answer nests the same envelope and changes in the same commit
  ([Routes and the CLI](#routes-and-the-cli)). So do the tests, fixtures, and goldens
  that name either route, `tests/golden/cli-github-pulls-refresh.txt` among them, and
  the parity rows `github.pulls-panel`, `github.pulls-watch`,
  `github.background-freshness`, `github.pulls-row-lines`, `github.pulls-stack-lines`,
  and `github.pull-summary-brief`.
- [ ] Make the five controller changes under [Browser Data Model](#browser-data-model),
  behind a measured pair on the Pulls tab.
- [ ] Add the object store with its default table and the read, registration, and write
  calls of `mb.objects` in the `sdk-views` bundle, and the list host as an on-demand
  bundle prefetched once the Pulls panel mounts, at the tiers under
  [Performance](#performance).
- [ ] Register the pull request’s `wide-row` view, and mount the wide list at `/pulls`
  in place of the placeholder, sharing the Pulls tab’s filter and collection.
- [ ] Add the object model’s architecture document,
  `docs/project/architecture/arch-object-model.md`, linked from Architecture and
  `docs/project/README.md`: the shared definitions, the shapes, the store, the list
  host, and the pull request projection.
  Its contract table and its declarations table arrive in Phase 2, with the contracts.
- [ ] Record the wide list’s measured row estimate and overscan; add the design-system
  sections for object views and for a list in the pane, sized by
  [Text Roles](../../../design-system.md#text-roles); register the map and the parity
  rows.
- [ ] Draw the `/pulls` page under the view header, through the SDK frame that mb-7t5s
  builds, which lands first ([Decision 12](#decision-12-how-a-view-is-defined)).

### Phase 2: Core Types and the Folder Page

Phase 2 adds the core types and, by [Decision 22](#decision-22-the-first-slice) D, the
contract half for every type.

- [ ] Add the `File`, `Folder`, and `Commit` models with adapters over the tree, event,
  recent, and pinned-revision feeds, and conform the Git log: its rows, its `commits`
  and `cursor` renamed to `rows` and `next_after`, and its times as UTC strings with
  their readers in `static/git-panel.js`, as [Decision 8](#decision-8-timestamps)
  requires. The change to the log’s times lands behind a measured pair on the Commits
  tab. Take the inventory provider’s decisions as #507 records them: a file’s identity is
  its byte-exact canonical name (D10, D18); a folder’s `totals.complete` says “complete
  with issues” apart from “still discovering” (D1), where a boolean cannot; the folder
  adapter drops objects under a subtree the provider reports removed (D20); and the
  `types` facet is projected from the tallies the provider’s contract owns (D22).
- [ ] Add the object registry, and the contracts for the pull request and the core
  types, with compiled schemas, a corpus, and the drift and corpus checks.
  The corpus is shaped like cached rows and written by the production writers from the
  synthetic fixture accounts of `tests/github_pull_fixture.py`, building on the cache
  home `tests/test_github_drawn_from_disk.py` already builds, and it settles the open
  items under [Summary and Facets](#summary-and-facets).
- [ ] Add `[[object_type]]`, `[[object_view]]`, and `[[collection]]` to the manifest
  schema, with their load-time validation and `metab --doctor` output.
- [ ] Add `GET /api/object-types`, the `object:` and `shapes:` lines in `--show`,
  validation in `--api`, and the two parity rules.
  The `object:` line exists already if the implementation map’s groundwork or the view
  slice landed first, and the registry route then takes over the view slice’s table of
  types and their object routes.
- [ ] Extend `docs/project/architecture/arch-object-model.md` with a table of contracts
  and a table of declared types, views, and collections, each naming its check.
  `devtools/check_artifact_contracts.py` compares only the cache’s registry with
  `docs/project/architecture/arch-repository-cache.md`
  (`devtools/check_artifact_contracts.py:10`, `:19`). It is changed once, to take a list
  of pairs, since the view model’s registry adds a pair too, and it gains this one: the
  object registry that `objects/registry.py` builds, and the document’s contract table.
  A test compares the declarations table with `/api/object-types`.
  [Architecture Documents](../../../development.md#architecture-documents) asks for both
  in the change that registers the surfaces.
- [ ] Give the Files view and the freshness vocabulary a retry state for a moved
  inventory version, which #520 answers as `503 inventory_version_moved` with
  `Retry-After: 1`, if that lands first.
- [ ] Add a **Files** view to the `folder` kind: the folder’s children as wide rows,
  read from `/api/tree`.
- [ ] Register the commit’s `card`, from the compact commit summary, and a `card` for
  the pull request, with the `card` frame, when their first real use lands and not
  before ([Decision 11](#decision-11-the-set-of-shapes)): the `/recent` page, in the
  Recent tab plan’s R4.
- [ ] Add Files to
  [Folder Views Are Tabs](../../../design-system.md#folder-views-are-tabs), which names
  only Overview, Treemap, and a future Files, with its key.
  `F` is the Files tab’s shell letter (`keymap.py:68`), so the Files view takes the next
  free letter of its label by
  [Scopes and Collisions](../../../design-system.md#scopes-and-collisions), `I`. The
  Recent tab plan takes `R` as its tab’s shell letter, so no folder view takes `R`.
- [ ] Document the surface in [Plugin Authoring](../../../plugins.md), and extend the
  object model’s architecture document with the core types and their tables.

### Phase 3: Converge the Existing Surfaces

Each item is independent, lands behind a back-to-back measurement against the code it
replaces, and may be declined.

- [ ] The pull-request page reads the object: its view header from the object’s header,
  and its commits, discussion, and changed files as collections; the store’s merge
  replaces `withListedState`.
- [ ] The Pulls panel’s rows become `nav-row` views on the list host, with their change
  line as a facet line and their stack headings as sections with a `describe` of their
  own.
- [ ] Quick Search results become references, the `pulls` route’s search answer
  conforms, and the pull-request provider moves to the plugin.
- [ ] The commit row and summary become views of the commit.
- [ ] The Files tree’s two row builders become one view of the file and folder.

## Testing Strategy

- **Contracts:** the schema drift check, the corpus with positive and negative cases,
  and the round trip, for a source checkout and an installed wheel.
- **Producers:** every projection branch validated in tests; every collection route’s
  golden validated before normalization.
- **Views:** a browserless session per plugin prints each view’s description of each
  corpus object, pinned as a golden; each view has an interaction row.
- **Store and list host:** browserless sessions for merging, generations, paging,
  offers, disclosure, and the keyboard contract, in the manner of `tests/dom/`.
- **The Pulls panel:** its existing sessions and goldens, reread after the `pulls` rows
  and the controller change, not regenerated blind.
  The panel’s rows are not redrawn in Phase 1.
- **Paint:** focused real-browser tests for the wide row’s grid, the stable box, and the
  alignment with the reading column, as `tests/test_folder_overview_alignment.py` does
  for Overview.
- **Design vocabulary:** the list host joins the row-collection registry, and the wide
  row and card join the checks on row height, hover, and chevron.
- **View model:** the view model plan’s
  [Testing Strategy](plan-2026-11-18-view-model-and-view-state.md#testing-strategy).
- **Performance:** performance-loop rounds for the Pulls tab before and after the change
  to what its route answers and its controller holds, for `/pulls` (first paint from a
  held collection, scroll, and return), and for each Phase 3 item, as
  [the web performance framework](../../../web-performance-framework.md) sets out.

## Rollout Plan

Each phase ships in a release with no flag: the pull requests page replaces a
placeholder, and the folder’s Files view is an addition.
A phase is more than one stack of pull requests, and the
[implementation map](plan-2026-11-18-object-model-implementation-map.md) divides each.
The conformant `pulls` rows change an internal route with its only readers, noted in
`CHANGELOG.md` as the manifest additions are.
Phase 3 items ship singly.
The view model and the Recent tab ship as their own plans set out.

## Open Questions

- **How large can a folder’s Files view be?** A directory with very many direct children
  arrives as one tree response today; the
  [flat-tree plan](plan-2026-09-15-flat-tree-delivery-cost.md) owns that cost, and the
  view windows what it is given.

- **Does a folder’s Files view follow the navigation filter?** The tree’s responses are
  keyed by the filter, and inside a Group by section by the group too
  (`static/app.js:2773`).

- **Is a symlink a file with a flag, or a third core type?** The inventory types it as
  its own leaf (`fs_record.py:46`).

- **Should a commit gain a kind,** so its page header is a registered page view and not
  shell code? The shared header (#487, and mb-7t5s once it lands) gives the commit page
  the same frame without one, which weakens the case.

- **Does the header carry a web address?** #552 ends the view header with a GitHub link,
  built in JavaScript; `GithubUrlReducer.web_url` builds the same address on the server.
  An optional `web_url` on the object would let every view and the CLI reach it.

- **Should the CLI print an object as a self-describing artifact?**
  `--api --format yaml` exists; with a `softschema:` header its output would validate
  with the `softschema` command.
  It is the one YAML artifact stage [Decision 1](#decision-1-what-describes-an-object) A
  could point to. Decisions 1 and VM-8 were taken without answering it, and the view
  model adds an argument for it
  ([Decision VM-8](plan-2026-11-18-view-model-and-view-state.md#decision-vm-8-the-schema-form)).

- **Are generated type declarations worth a generator,** or does a test that compares
  hand-written declarations with the schema’s properties suffice?

- **Should a plugin type be allowed a `permissive` contract** while it settles?
  The registry admits and writes only `enforced` today
  (`plugin_loader/artifact_contracts.py:399-400`, `:499`), so Decision 1 A brings no
  maturity ladder until it does.

- **Do a container’s children become a collection?** The children hook already answers a
  small list of rows.

The view model’s open questions are in
[View Model and View State](plan-2026-11-18-view-model-and-view-state.md#open-questions),
and what each Recent source costs is among
[The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md#open-questions)’s.

## References

- The companion plans:
  [View Model and View State](plan-2026-11-18-view-model-and-view-state.md),
  [The Recent Tab](plan-2026-11-18-recent-tab-updates-and-events.md),
  [Plugin Authoring for Objects, Views, and View State](plan-2026-11-18-plugin-authoring-objects-views.md),
  [Agent Interface for Objects and View State](plan-2026-11-18-agent-interface.md), and
  the [implementation map](plan-2026-11-18-object-model-implementation-map.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md),
  [Plugin System](../../architecture/arch-plugin-system.md),
  [Browser Shell](../../architecture/arch-browser-shell.md),
  [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md),
  [Git](../../architecture/arch-git.md),
  [Parity Registry](../../architecture/arch-parity-registry.md),
  [Open Modes](../../architecture/arch-open-modes.md),
  [Recent Targets](../../architecture/arch-recent-targets.md), and
  [Inventory Provider](../../architecture/arch-inventory-provider.md)
- [Design System](../../../design-system.md): Rows and Disclosures, The Pulls Tab, Git
  Commit Summary, Page Headers, Text Roles, Navigational Row Collections, Folder Views
  Are Tabs
- [Plugin Authoring](../../../plugins.md) and
  [Rendering Large Content](../../../large-content-rendering.md)
- [A Machine-Readable Contract for the API Envelopes](plan-2026-08-30-api-schema-and-contract.md)
  and [Functional UI and CLI Parity](plan-2026-09-10-functional-ui-cli-parity.md)
- [SoftSchema](https://github.com/jlevy/softschema): its guide and specification

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
