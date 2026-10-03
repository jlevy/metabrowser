# Plan: GitHub Pulls Tab for Mirrors and Local Checkouts

**Status:** Planned, not started.
Nothing this plan designs exists yet: no route, model, tab, or test.
Work starts after the v0.12 stack lands (`mb-n2ro`), as a new stack of pull requests,
each merged to `main` before the next one starts.
[Delivery](#delivery) lists the steps, and
[Open Decisions for the User](#open-decisions-for-the-user) lists what is settled first.

This plan builds on the [thin-mirror plan](plan-2026-09-23-v012-thin-mirror.md), which
stays the authority for the mirror, `gh`, and pull-request records.
It replaces the list, panel, and checkout-attachment designs in
[GitHub Provider and Pull Requests](plan-2026-08-27-github-provider-and-pull-requests.md),
which predate the thin mirror (beads `mb-lnkl`, `mb-iw1v`, `mb-cbak`; this plan is
`mb-qftx`).

## Goal

Open a GitHub repository and find its pull requests in a **Pulls** tab beside Files and
Git.
Select one and read it in the same page: description, conversation, reviews, checks,
and Files changed.

This works for a repository opened from a GitHub URL, which is a mirror in Metabrowser’s
cache, and for a checkout the user already has on disk.
Like every other view, the list opens from the cache at once, refreshes in the
background, and keeps working offline.

### Non-Goals

- Issues, Actions, and releases.
- Review submission, comments, merging, or any other write to GitHub.
  Every request this plan adds is a `GET` through `gh api`.
- GitHub Enterprise hosts, and SSH as a transport.
  A checkout whose remote is an SSH address on github.com is still identified, because
  identity is read from configuration and nothing is fetched over SSH.
- Inline review anchoring in the diff.
- Search across pull requests, and sort orders other than GitHub’s default.
- A public plugin SDK for navigation panels.

## Rules This Work Keeps

The thin-mirror plan’s [Principles](plan-2026-09-23-v012-thin-mirror.md#principles)
apply unchanged. Five rules follow from them and from the user’s decisions, and every
step is reviewed against them:

- **A plain folder starts no `gh` and no network.** Serving a folder that is not a
  GitHub repository loads none of the cache or the GitHub plugin and spawns nothing.
- **A checkout uses the network only when the user opens the Pulls tab.**
- **Nothing is written to the user’s repository.** No fetch, ref, index, or
  configuration write; Metabrowser’s own cache is the only place it writes.
- **Pull-request text is always inert**, whatever trust profile the folder has.
- **Lists are bounded, and their counts are honest.** A count is what was fetched, and
  the tab says when GitHub has more.

## What Exists and What Is Missing

Every statement here was checked against the v0.12 stack tip on 2026-10-01. Code is
cited by module and function, since line numbers go stale.
Paths are under `src/metabrowser/` unless they begin with `tests/`, `devtools/`, or
`explorations/`. Step 1 starts by checking these again, because the stack can still
change before it lands.

### What Exists

- **Per-pull-request records.** `builtin_plugins/github/pull_record.py` defines
  `PullRecord`, its bounds with their measurements, and `read_pull_record` and
  `write_pull_record`. Both take the application home and a source slug, not a store, so
  a record can be read and written where no mirror exists.
  `cache/paths.py` names the files: `source_pull_record` and `source_pull_refresh`.
- **The network job for one pull request.** `refresh_pull_request` in
  `builtin_plugins/github/pulls.py` reads the account, the pull request and its lists,
  the account again, then fetches `refs/pull/<n>/head` and computes the comparison.
  The last two need a store: `fetch_pull_head` and `comparison_endpoints` in
  `cache/pull_refs.py` take a `PublishedSource`.
- **The pull-request page.** `builtin_plugins/github/pull-page.js` holds the page
  (`describePull`, `createPullController`, `mountPullPage`), and `static/pull-route.js`
  holds its host. `createPullPageHost` already opens another pull request’s page in
  place: its `open` takes any number and pushes `/pull/<n>`. `pull_shell` in `server.py`
  serves the shell for any valid number.
- **Inert text.** `render_part` in `builtin_plugins/github/pull_markdown.py` passes
  every rendered text through `inert_html.harden`, with no branch on the trust profile,
  and the page rebuilds the result through `static/inert-html.js`.
- **A refresh coordinator on every server.** `lifespan_refresh` in `mirror_refresh.py`
  creates a `RefreshCoordinator` for a folder as well as a mirror.
  Only a mirror gets a `MirrorSession`.
- **Typed `gh` failures.** `builtin_plugins/github/gh.py` names `gh_missing`,
  `gh_too_old`, `not_logged_in`, `rate_limited` (with the reset time),
  `not_found_or_private`, `network_error`, and `gh_failed`; `PullDataState` in
  `pulls.py` adds `account_changed`, `cache_unwritable`, and the fetch states.
- **Repository identity in every page.** `index` in `server.py` writes
  `window.METABROWSER_REPOSITORY_CONTEXT` into the shell.
  For a mirror it comes from the provider (`GithubProvider.repository_context`). For a
  folder it comes from `discover_repository_context` in `repository_context.py`, which
  reads the `origin` remote from the checkout’s Git configuration with bounded file
  reads and no Git process, including when the served folder is a subdirectory of the
  working tree. The plugin SDK publishes it as `metabrowser.repository`.
- **A source with no store is already a named state.** `_source_row` in
  `cache/projection.py` reports a source directory that has `source.yml` and no
  `store-alias.yml` as `unattached`, `tests/golden/cli-api-cache.tryscript.md` pins it,
  and `_attach_existing_source` in `cache/acquire.py` attaches a store to such a
  directory when the source is acquired later.
  Nothing publishes one on purpose today: `_publish_source_directory` writes both
  records.

### The Navigation Tabs Are Internal

`registerNavPanel`, `ensureNavPanelElements`, `activateNavPanel`, and `removeNavPanel`
in `static/app.js` are the tab registry.
They are published on `window.MetabrowserShell`, which that file describes as an
internal boundary for core modules and not the plugin SDK. `static/git-panel.js` is its
one user outside `app.js`: it arrives in the `shell-tools` on-demand bundle after the
first tree settles, asks `/api/git/repo`, and registers the Git tab if the root is a
repository.

Three facts shape the design:

- A panel has `onFirstShow` and `onShow` and no hook for being hidden.
- The GitHub plugin’s JavaScript is loaded only when its `pull-request` kind is needed,
  through `metabrowser.ensureKindAssets`, so it cannot register a tab at startup, and a
  plugin may not reach `window.MetabrowserShell` (AGENTS.md, Browser and Plugin
  Boundary).
- The thin-mirror plan retired the public `registerNavPanel` declaration for the alpha;
  [Views, Models, and Routes](../../architecture/arch-views-models-routes.md#planned-plugin-registration-surfaces)
  keeps its row as background.

### One Pull Request per Server

A server serves at most the one pull request its URL named.
The assumption lives in these places:

| Where | What it assumes |
| --- | --- |
| `cache/urls.py`: `RepositorySelection.pull_request` | A URL names at most one pull request. This stays true |
| `cli/git_pin_cli.py`: `_select`, `_serve_selected`, `_one_shot_pin` | A companion is built only when the URL names a pull request, and one number and one companion are passed to `serve_mirror` |
| `cache/providers.py`: `RepositoryProvider.served_pull_request`, `served_pull_request_for` | The provider is asked for one number |
| `mirror_refresh.py`: `serve_mirror`, `MirrorSession` (`companion`, `request_companion_refresh`, `companion_refreshing`, `_companion_job`, `_refs_to_keep`), `FreshnessFields.pull_request` | One `CompanionRefresh` and one number for the server’s lifetime |
| `source_routes.py`: `SourceStatus.pull_request` | The status reports that one number |
| `builtin_plugins/github/served_pull.py`: `ServedPull` | Refresh state for one number |
| `builtin_plugins/github/pull_route.py`: `served_pull_of`, `served_pull_view` | The routes read the session’s one companion and take no number. A server opened on a repository URL answers `absent` with `no_pull_request` |
| `builtin_plugins/github/sidekick.py`: `pull_refresh_handler`; `pull_markdown.py`: `render_part` | `409 no_pull_request` when the URL named none |
| `builtin_plugins/github/pull-page.js`: `describePull` | A page for another number shows `other_number`: “This server serves pull request #N” |
| `static/source-freshness.js`: `describe` | The freshness row links one pull request |
| `cli/show_cli.py`: `_require_served_pull` | `--show /pull/<n>` refuses any other number |

Some parts are already keyed by number and need no change: the parsed-record cache in
`pull_route.py` (`cached_pull_record`, bounded by `_MAX_PARSED`), the coordinator key
`<store key>:pull/<n>` in `ServedPull.key`, the page host, and the ref selector’s label
for any `refs/pull/<n>/head` in `static/source-ref-selector.js`.

Two existing behaviors matter to the design:

- **Browse code switches nothing.** On the page it is a plain link to the root of
  whatever commit is served.
  The switch is a separate offer, `headOffer` in `describePull`, shown when the served
  commit is not the record’s head; it posts the head ref to `/api/source/pin`.
- **The reset time is reported, not obeyed.** `ServedPull.is_stale` holds a failed
  refresh back by the freshness window alone and does not read `reset_at`.

### The `gh` Runner Pages by Explicit Page Number

`gh_api` in `gh.py` issues one `gh api --include` request for one path and neither
paginates nor caches.
Callers name each page.
`_read_list` in `pulls.py` appends `?per_page=<size>&page=<n>`, steps the page size down
when a page exceeds `GH_API_MAX_BYTES`, stops at a cap, and sends `If-None-Match` only
with the first full-size page; `GhResponse.has_next_page` reads `rel="next"` from the
`Link` header.

Two details matter for a list:

- `_read_list` builds the query itself, so a path that carries its own query (the list’s
  `state` and `sort`) needs the helper to take those as parameters.
  `_API_PATH` already admits them.
- `_refusal` words a `403`, `404`, or `410` as a missing pull request.
  A list needs repository wording for the same state.

### What Is Missing

- Any list of pull requests: no request, model, file, or route.
- Routes that name a pull-request number, and a way to fetch one the URL did not name.
- The tab.
- Any path from a folder server to pull-request data: with no `MirrorSession`, every
  pull route answers `no_pull_request`.
- A test that a folder starts no `gh`. The guarantee today is indirect: the import
  boundary in `tests/test_plugin_public_api.py` (`_ROUTE_TABLE_ONLY`) keeps `gh.py`
  unloaded on a folder, and the `_no_real_gh` fixture in `tests/conftest.py` puts a
  failing stand-in first on `PATH` and names, in the run’s summary, each test whose call
  reached it. That summary does not fail the run.
- An address for the list.
  `devtools/check_parity.py` requires every kind a built-in manifest declares to appear
  as `kind: <id>` in a golden, which `--show` prints for an address.

## Design

### List Data

**Requests.** One `gh api` call per page through `gh_api`:

```
repos/<owner>/<repo>/pulls?state=<open|closed|all>&sort=created&direction=desc&per_page=100&page=<n>
```

- The order is GitHub’s default, newest first, which is also descending number order
  ([List pull requests](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests)).
  Rows are therefore ordered and deduplicated by number.
- The job reads the account with `gh_account` before and after the pages, as
  `refresh_pull_request` does.
  A list read while the active account changed is discarded as `account_changed`.
- The paging loop is `_read_list`, moved to a shared module and given query parameters.
  It is moved, not copied.

**Rows.** A row keeps only what the tab shows: `number`, `title`, `state`, `draft`,
`merged_at`, `author`, `created_at`, `updated_at`, `closed_at`, `base_ref`, `head_ref`,
`head_repository`, and `labels` (names only).
The description, the embedded repository objects, and every URL are dropped.
GitHub’s list items are expected to carry `merged_at` and not the single-pull `merged`
flag, so “merged” is derived from `merged_at`; the recorded fixture in step 1 confirms
the item shape.

**Model and file.** A Pydantic model validates on write and parses on read, as
`PullRecord` does. The proposed module is `builtin_plugins/github/pull_list.py`.

- One file per state: `cache/sources/<slug>/pulls/list-<state>.json`, with
  `list-<state>.refresh.json` beside it for how the last refresh ended (the existing
  `PullRefreshStamp`). `cache/paths.py` names both.
  A list name cannot collide with a record’s `<n>.json`.
- Fields: `schema_version`, `source`, `list`, `fetched_at`, `reader`, `pages`,
  `complete`, `truncated`, `etags` (one per full-size page), and `rows`.
- `PULL_LIST_SCHEMA` starts at 1. A mismatch refetches; nothing migrates.
- It is written with the home’s private atomic write and read with a size bound.

One file per state, and not one merged index, because each file is then a prefix of one
GitHub listing in GitHub’s order, and `complete` has one meaning.
A merge of separately bounded open and closed lists would be complete only above the
higher of their lowest numbers, which no label could say plainly.

**Bounds, measured before they are set.** Step 1 measures and records beside each
constant, as `pull_record.py` does:

- the bytes and seconds of one list page, for `per_page` of 100 and smaller, on the
  repositories of the ten pull requests the record bounds were measured on.
  A page is expected to run to megabytes, since each item embeds both repositories and
  the description; this decides the default page size and whether `GH_API_MAX_BYTES`
  needs the step-down often;
- the largest row and the label count per row, for the row and label bounds;
- the open and closed counts of those repositories, for the rows kept per state;
- the file size at that cap, for the read bound.

The starting hypothesis is ten pages per state, the shape `MAX_ISSUE_COMMENTS` took.
The measurement decides; [Open Decisions](#open-decisions-for-the-user) item 6 is the
user’s part of it.

**Honest counts.** GitHub’s list gives no total.

- The count shown is the number of rows fetched.
- `complete` is false when the last page fetched had a next page, and the tab then says
  that GitHub has more and offers the next page.
- `truncated` is true when a bound cut a row’s text or dropped an item that could not be
  read, and the tab says so.

**States.** `open`, `closed`, and `all` are three lists.
Only the list the reader is looking at is fetched.

**Paging.** There are two levels:

- The route answers a window of the cached rows, by `limit` and `after` (a row’s
  number), so a transcript stays small and the browser appends pages of plain rows.
- When the cached rows run out and the list is incomplete, a reader’s **Load more**
  fetches the next GitHub page.

**Staleness and background refresh.** The list uses `FRESHNESS_WINDOW_S` and the
existing `RefreshCoordinator`, under a key of its own per source and state.

- A refresh rereads every page the file holds, each full-size page with its own
  `If-None-Match`. A `304` reuses that page’s rows, and GitHub documents that it does
  not count against the primary rate limit
  ([best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)).
- The list is assembled over the job’s duration and is not atomic.
  A pull request that opens or closes between two page reads can appear twice, which the
  number dedupes, or be missed until the next refresh.
- A failed refresh leaves the file as it was.
  The next automatic attempt waits a window, and after `rate_limited` it waits for
  `reset_at`. The same rule is applied to `ServedPull` in step 2.
- A list job never touches a store, so it does not take the mirror’s fetch turn.

**Typed failures.** The stamp carries the states `gh.py` already names, plus
`account_changed` and `cache_unwritable`. No new state is needed.

**Another reader.** The file names its reader, `gh:<login>`.

- A list fetched by another account is shown as it is, labelled with that reader, and
  treated as stale. This matches the thin-mirror rule that cached private content stays
  viewable after a logout or an account switch; the cache is owner-only.
- The next successful refresh replaces the whole file.
  Pages from two readers are never joined, and ETags are reused only for the same
  reader, so **Load more** under a new account starts again from the first page.

**No Git refs.** Listing calls `gh` only.
It needs the home, the slug, and the owner and repository, never a `PublishedSource`.

**Routes.** Both are data hooks of the GitHub plugin, one path segment each, with
handlers in `sidekick.py` that import the rest only when called:

| Route | Answer |
| --- | --- |
| `GET /api/plugin/github/pulls?state=&limit=&after=` | From the cache alone: `state` (`absent`, `pending`, `current`, `stale`), `reason`, `source`, `list`, `fetched_at`, `reader`, `fresh_for_s`, `refreshing`, `last_refresh`, `fetched`, `complete`, `truncated`, `limit`, `next_after`, and `rows`. It carries an entity tag, as the pull route does |
| `POST /api/plugin/github/pulls-refresh` with `{"state": …, "more": false}` | Starts or joins the list’s refresh and answers `202` at once with the envelope and its `status_route`. `"more": true` extends the list by one GitHub page |

### Opening Any Pull Request from a Repository Server

This is the riskiest step.
It changes core (`mirror_refresh.py`), three routes, and every pull-request transcript,
so it is its own pull request with its own independent review.

**Routes name the number.**

- `GET pull?number=<n>`, `POST pull-refresh` with `{"number": n}`, and
  `GET pull-markdown?number=<n>&part=<part>`.
- `number` is required.
  These are internal contracts that ship as one artifact, so the page, the CLI, and
  every transcript change in the same commit, with no fallback to “the served one”.
- `no_pull_request` and the page’s `other_number` state go away.
  A valid number with no record answers `absent` with `not_cached`.
- `--show /pull/<n>` reads the same route, and `_require_served_pull` is removed.

**A provider-kept set replaces the single companion.**

- The provider hands the server one object for the repository, for any GitHub mirror and
  not only when the URL named a pull request.
  `RepositoryProvider.served_pull_request(published, number)` becomes a method that
  returns that set.
- The set gives a `CompanionRefresh` for a number.
  It keeps the in-memory state of `ServedPull` (record time, last outcome, last attempt)
  for a bounded number of pull requests and reads the rest from disk on demand, as
  `served_pull` does today.
  The bound is needed because the numbers are request text, which is why
  `MAX_REMEMBERED_MISSES` bounds the selections it remembers.
- `MirrorSession` runs any companion’s refresh as a coordinator job under `_fetch_turn`,
  which is the body of `_companion_job` given the companion.
- The job is `refresh_pull_request`, unchanged: the record and `refs/pull/<n>/head`
  together, under the key `<store key>:pull/<n>`, so concurrent requests join it.

**One attended pull request.** `MirrorSession` keeps one number: the one the URL named,
replaced whenever a pin switch serves `refs/pull/<n>/head`.

- Its companion is what `is_stale`, `request_refresh`, `request_commit_fetch`, and
  `_missing` use, exactly as they use `companion` today.
  This keeps the behavior a page of code on a pull request’s head depends on: the
  refresh that finds a newer head.
- `_refs_to_keep` and the status route’s `pull_request` report it.

So the companion-refresh design stays.
It is generalized from one fixed companion to one attended companion chosen from a
bounded set, plus a direct start of any number’s refresh by the plugin’s `POST` route.

**What starts a fetch.**

- A pull request with no record is fetched only by a reader’s action in the shell’s own
  chrome: selecting a row in the Pulls tab, or pressing **Fetch** on its page.
  An address alone shows what is cached, whether it was typed, followed from rendered
  content, or reached by Back.
  So nothing a link can do adds to the cache.
- A pull request with a record refreshes in the background when its page is visible and
  the record is stale, as a stale mirror does.
  The page’s controller asks for it, and the server holds each number to one attempt per
  window.

**How many refreshes run at once.**

- `MAX_CONCURRENT_REFRESHES` bounds network jobs across the mirror, the lists, and every
  pull request.
- Pull-request jobs and the mirror’s own fetch take turns at the store through
  `_fetch_turn`.
- A new bound limits how many distinct pull-request jobs may be queued or running.
  A request past it is refused with a typed state and starts nothing.
  The bound is set from the measured duration of one refresh, which is at least eight
  `gh` processes and one `git fetch`.

**Status, freshness row, and ref selector.**

- `/api/source/status`: `pull_request` is the attended number; `stale` and `refreshing`
  cover the mirror and that pull request, as now.
- The freshness row links the attended pull request, as now.
- The ref selector shows “Pull request #n” while the pin is that head, as now.
  It still lists only branches and tags; the Pulls tab is how a pull request’s code is
  reached.

**Browse code.** Opening a pull request from the list does not move the pin, since one
server has one pin and other tabs share it.
The pull envelope gains the pin’s ref, and the page has three cases:

| The served commit | What the page offers |
| --- | --- |
| Is the record’s head | **Browse code** is a link to the root, as now |
| Is on this pull request’s head ref and behind the record’s head | The existing offer to switch to the newer head |
| Is anything else: a branch, a tag, another pull request | **Browse code** is a button that posts this pull request’s head ref to `/api/source/pin` and then opens the root. No warning is shown, because nothing is wrong |

**View file.** View file switches the pin by commit ID. `resolve_pin` then serves a
commit under a pull request’s head ref when it is that ref’s tip, for any pull request
the mirror holds and not only the attended one, and the switch makes that pull request
the attended one. The lookup is one `for-each-ref --points-at` over `refs/pull/`, whose
cost step 2 measures on a mirror with many fetched heads.

**Back and Forward.**

- Selecting rows mounts pages through the page host, which pushes `/pull/<n>`. Back and
  Forward between them use the existing `pullHistoryAction`. No pin moves.
- **Browse code** from a pull request’s page switches the pin and loads a new document.
  Back then lands on a page rendered for the earlier pin.
  The history guard in `static/source-pin-guard.js` asks the status route once and
  reloads the page, as it does after any switch.
- A data request from a page whose pin was replaced is refused `pin_changed` by
  `SourcePinGuard`, as now.

### The Tab

**When it appears.** The tab appears when the page’s repository context is present,
which is when the served root is a GitHub mirror, or a checkout whose `origin` is on
github.com and whose `HEAD` names a commit.

- The context is already in the shell, so the decision costs no request, no Git, and no
  `gh`.
- A plain folder has no context and gets no tab.
- On a checkout served from a subdirectory the tab still appears, because pull requests
  belong to the repository; the Git tab’s rule, that the served root must be the working
  tree’s root, does not apply.
- `discover_repository_context` admits owner and repository spellings the GitHub
  plugin’s URL grammar refuses.
  The list route validates with the plugin’s grammar, and the tab then says the remote
  is not one it can list.

**Who owns what.** The shell owns the tab, and the plugin owns the view, as with the
pull-request page.

- A small core module, proposed as `static/pulls-nav.js`, joins the `shell-tools`
  bundle. It registers the panel through the internal `registerNavPanel`, and on first
  show it loads and mounts the view a plugin registers for a `pull-request-list` kind.
- The GitHub plugin declares that view in its manifest and registers it with
  `metabrowser.registerView`. Its code is `builtin_plugins/github/pulls-panel.js`.
- The shell hands the view the page host’s `open`, and says when the panel is shown and
  hidden. The registry gains an `onHide` hook for that.
- No new public SDK surface is added.
  The shell holds no GitHub code, and the plugin reaches no private global.

**The list’s address.** `/pulls`, with `?state=` for a filter, is the list with no pull
request selected, as on GitHub.

- The shell shows the Pulls tab at `/pulls` and at `/pull/<n>`, as it shows the Git tab
  at a commit’s address.
  Selecting the tab by hand does not change the address, as with the other tabs.
- `--show /pulls` prints `kind: pull-request-list` and a summary of the list envelope,
  which is the kind’s evidence for the parity gate.
- It belongs to the pull-request address space and adds no startup script.
  On a plain folder it is a page whose own request says there is nothing to list, as
  `/pull/<n>` is today.
- Opening `https://github.com/<owner>/<repo>/pulls` with `metab` is a natural follow-on.
  It is left out: the URL reducer refuses that shape today, and accepting it changes the
  URL grammar.

**The lazy `gh` check.** There is no separate check and no status route for `gh`.

- The first thing a list refresh does is read the account, so the first refresh is the
  check. `gh_executable` is a `PATH` lookup and spawns nothing.
- The tab is never hidden for a `gh` problem.
  It shows the cached list if there is one, and the state with what to do:

| State | What the tab says |
| --- | --- |
| `gh_missing` | Install GitHub CLI and sign in. A cached list still shows |
| `gh_too_old` | The installed `gh` is older than `GH_MIN_VERSION`; update it |
| `not_logged_in` | Run `gh auth login` |
| `rate_limited` | GitHub’s limit lifts at `reset_at`; no automatic attempt runs before then |
| `network_error` | Offline or GitHub unreachable; the list is as fetched at its time |
| `not_found_or_private` | The repository was not found, or the signed-in account cannot read it |
| `account_changed`, `gh_failed`, `cache_unwritable` | The message the job recorded, and **Retry** |

**Rows.** Each row is a link to `/pull/<n>`, so a new tab and a copied address are the
browser’s own.

- It shows the number, the title, a state badge (open, draft, merged, closed, in the
  page header’s words), the author, the updated time, and the head and base names.
- The row for the page that holds the pane is marked current.
- All of it is written as text, never parsed as markup.
- Rows follow the design system’s row contract and tooltip rules.

**Filters.** Open, Closed, and All.
Each is its own cached list, and Open is the default.

**Keyboard and accessibility.**

- The tab is a `role="tab"` button like the others.
- The list has roving focus: Up, Down, Home, and End move, and Enter opens, as in the
  Git tab. **Load more** is a button after the last row.
- The list’s accessible name carries the honest count.
- Refresh states are announced in a polite live region, as the freshness row’s are.
- The contextual keyboard help gains the panel’s keys.

**Loading tier and the startup budget.**

- Nothing is added to the startup scripts.
  The host is in `shell-tools`, which loads after the first tree settles; the Git tab
  appears at the same moment.
- The view’s code is on demand, fetched on first show.
- `devtools/check_startup_scripts.py` proves it on every `make lint-check`: it fails on
  any script requested before `DOMContentLoaded`, and it reports the current totals
  against `explorations/performance-loop/performance-budgets.toml`.

**Large lists.** The tab appends plain rows a page at a time, as the ref selector does.
Step 3 measures in a real browser what the row cap costs to render and to keep, by the
method in [rendering large content](../../../large-content-rendering.md).
If the cap’s worth of rows is past the budget, the panel uses the Git tab’s windowing
module.

**What is prefetched.**

- On a mirror, after the first tree settles: the view’s code and the cached list
  envelope. Both are local.
- On a checkout: nothing until the tab is opened.
  Even the cached read would load the cache into a folder’s server.
- A cached record is read when its row takes focus or the pointer, which is a local
  `GET` that runs no `gh`.
- The network refresh starts when the tab is first opened, on a mirror and a checkout
  alike. Step 3 also measures starting it at a mirror’s open, which is what “prefetch by
  default” asks for; [Performance](#performance) gives the accept rule.
- No spinner appears before the `--loading-state-delay` token, through the existing
  `mb-delayed-loading` class.

### Local Checkouts

**Identity.** The repository is the one `discover_repository_context` already reads: the
`origin` remote, in any spelling it accepts, reduced to
`https://github.com/<owner>/<repo>` and lowercased by the plugin’s grammar.

- An HTTPS and an SSH remote for one repository therefore share one identity, the same
  one a mirror of that repository has.
- On a fork, `origin` is usually the fork, whose list is often empty.
  The tab names the repository it lists, so this is visible.
  [Open Decisions](#open-decisions-for-the-user) item 1 covers the alternatives.

**Shared records in the cache.** Lists and records are keyed by that identity and live
under `cache/sources/<slug>/pulls/`, shared by a checkout and a mirror of the same
repository.

- A read creates nothing: with no source directory the routes answer `absent`.
- The first write claims the slug and publishes a source directory holding `source.yml`
  and no `store-alias.yml`. That is the `unattached` state, which this plan makes a
  normal one. Acquiring the repository later attaches a store to the same directory, and
  the records are already there.
- That write creates the application home and its cache layout when they do not exist,
  as the first `metab <url>` does.
- Nothing about the checkout is recorded: no path, no branch.
- A record written without a store has no comparison, with the reason `no_store`. A
  server that has a store treats such a record as stale whatever its age, so its Files
  changed is not left unavailable.

**How the routes find the repository.** On a mirror, the routes reach the provider’s set
through the `MirrorSession`. A folder has none, so the plugin resolves the repository
for each request from the served root’s repository context, remembered until the root
changes, and from it the home and the slug.
Jobs run on the server’s `RefreshCoordinator`, keyed by the slug.

**No writes to the user’s repository.**

- Identity is read from files.
- Conversation, reviews, and checks need no Git objects.
- Every Git command run in the checkout is a read under `READ_POLICY`, as the Git tab’s
  are.
- No fetch, no ref, no configuration write.

**The page on a checkout.** The page works from the record alone.

- It has no pin, so it shows no **Browse code** and no switch offer; the working tree is
  not the pull request’s code.
- When the checkout’s `HEAD` is the pull request’s head, the page says so and links the
  root.

**Files changed.** Step 5 has two cases:

- **The commits are in the checkout.** The page checks for the base and head commits
  with a read-only Git command and shows the diff through the existing comparison route,
  from the merge base of the API’s `base.sha` and the head.
  That is the rule a mirror uses for closed and merged pull requests; for an open one it
  can differ from GitHub’s when the base branch has moved, and the page names the base
  it used. The comparison route requires the served folder to be the working tree’s root,
  and the page says so otherwise.
- **The commits are missing.** The page says so and writes nothing.
  It gives the command that opens the pull request from a mirror,
  `metab https://github.com/<owner>/<repo>/pull/<n>/files`, and the command that brings
  the commits into the user’s own repository, `git fetch origin pull/<n>/head`, for the
  user to run if they choose.
- **An in-page fetch into Metabrowser’s mirror** is the fuller form of that offer: a
  button that acquires the repository into the cache, fetches the head, and serves the
  diff from the mirror’s store.
  It needs two things nothing has today: acquisition inside a running folder server, and
  a diff served from a store that is not the served subject.
  It is a full clone, so it is always the user’s explicit choice, with the size shown
  first as `check_first_clone` reads it.
  [Open Decisions](#open-decisions-for-the-user) item 4 decides whether it is built.

**The alternates option.** A cache-side store could borrow the checkout’s objects
through `objects/info/alternates` and fetch only what is missing.
It is left out at first: a `gc`, a repack, or a move of the user’s repository can remove
objects the borrowing store depends on, which breaks the rule that no object Metabrowser
showed is ever lost.

**Network only when the user opens the tab.** Opening a folder makes no request today,
and that stays true.

- The list is read and refreshed when the user opens the Pulls tab.
- It refreshes in the background only while that tab is the visible panel of a visible
  page. Switching to Files stops it.
- A pull request’s page refreshes its own record only while it is shown.

**A trusted folder showing untrusted text.** A checkout is served under the trusted
profile by default, and a pull request’s text is written by anyone.

- The text renders through the same two inert layers under both profiles: the allowlist
  on the server and the rebuild from an inert template in the page.
  Neither reads the profile.
- A trusted folder’s page carries no Content-Security-Policy: `index` sends
  `untrusted_shell_csp` only when active content is off.
  On a mirror that policy is the second line behind the allowlist.
  On a checkout there is none, and a hole in the allowlist would run script in a page
  that can read the user’s files and, where editing is on, write them.
- So step 4 runs the hostile-content corpus under both profiles, with mutation checks,
  and has its own security review.
  [Risks](#risks) records the stronger alternative.

### Security and Privacy

- **Untrusted content.** Titles, names, labels, and bodies are GitHub’s users’ text.
  The list paints text only.
  Bodies go through the inert layers.
  Label colors are not used, so no value from GitHub reaches a style.
- **Credentials.** `gh` holds them.
  Metabrowser never reads, stores, or logs a token.
  `gh`’s standard output is never logged; on a failed run, the first bytes of its
  standard error are logged at debug level.
  No list, record, envelope, or stamp carries a credential, and a test asserts it over
  the written files.
- **What leaves the machine, and when.**
  - On a plain folder: nothing.
  - On a checkout: nothing until the Pulls tab is opened.
    Then `gh` asks api.github.com for the list of the repository named by `origin`, and
    for each pull request the reader opens.
  - On a mirror: the same, plus the Git fetch of `refs/pull/<n>/head` for a pull request
    the reader opens.
  - The requests name the repository and the pull request, and carry `gh`’s own
    authentication. Nothing about local files, paths, or branches is sent.
- **Route safety.** Every route that starts network work is a `POST` with a JSON body
  behind the same-origin guard and the JSON content-type rule, so content cannot reach
  it with a link, an image, or a form.
  Following a link can cause a refresh only of what is already cached, at most once per
  window per key. It cannot add a pull request to the cache.
- **Paths.** The new envelopes carry the canonical source URL and never a cache path, a
  store path, or the checkout’s path.
  The v0.12 mirror-name change (`mb-fndz`) lets one display field show where a mirror is
  stored. Whatever that field becomes, it stays the only place a cache location appears,
  and this work adds no other.

### Parity and Tests

Each route and state has a `metab` equivalent and a golden, per AGENTS.md.

| Surface | `metab` equivalent | Golden |
| --- | --- | --- |
| `GET pulls`: `absent`, `stale`, `current`, the window, an incomplete list, another reader | `metab <repo-url> --api '/api/plugin/github/pulls?state=open'` | A new tryscript transcript over a prebuilt home, which the parity gate counts |
| `POST pulls-refresh`: started, joined, `more`, and each typed failure | `--api … --data` | An in-process transcript with the fake `gh`, listing the `gh` calls made; and the failing one-shot shape in the tryscript, as `pull-refresh` has |
| `/pulls`, the list’s address and kind | `--show /pulls` | The list’s tryscript transcript. `_SHELL_ROUTES` in `tests/test_plugin_public_api.py` gains the address, so a plain folder’s page there loads nothing new |
| `GET pull?number=`, `POST pull-refresh`, `GET pull-markdown?number=` | `--api`, and `--show /pull/<n>` for any number | The existing pull transcripts, regenerated |
| The same routes on a checkout | `metab <folder> --api …` | A new tryscript transcript over a checkout fixture and a prebuilt home |
| The list file and its stamp | `--api` on the list route, and `/api/cache/source` showing `unattached` for a checkout’s source | The transcripts above |
| `/api/source/status` with an attended pull request that changes | `--api` after a pin switch | The source transcript |

**Browserless sessions.** Each runs the production JavaScript from the command line and
has a golden and a row in the functional-aspect table:

- the Pulls panel: `describe` and the controller in `pulls-panel.js`, covering the
  filters, the window, **Load more**, each `gh` state, polling while shown and none
  while hidden, and the open action;
- the panel host in `pulls-nav.js`: when the tab is registered, lazy mounting,
  replacement, and disposal;
- the page with numbered routes: the three Browse code cases, a not-cached page, and a
  page on a checkout.

**Fake `gh` fixtures.** `tests/github_pull_fixture.py` gains list pages, as scrubbed
real responses beside the existing ones, and scenarios for a full page with a next link,
a moved page, a `304`, each failure, and an account change.
It also gains a checkout: a clone of the stand-in origin whose `origin` URL is set to
the GitHub address, holding one pull request’s head and lacking another’s.

**Paint exemptions.** Building the panel’s DOM, scrolling, focus rings, and layout need
a rendered page. Each exemption row names the behavior, the session that owns every
decision behind it, and its focused evidence, as `github.pull-page-paint` does.

**Rules from the v0.12 test review.** They apply to every test in this work:

1. Every route golden pins standard output and standard error separately.
   `block` in `tests/golden_harness.py` does this for in-process transcripts.
2. No test asserts on source text.
3. No test repeats what a golden pins unless it adds independent evidence, and it says
   what that evidence is.
4. Every security or bounds test has a mutation check: the reviewer breaks the guarded
   code and sees the test fail.
5. Recorded fixtures are regenerated by `make golden-update`: each recorder is listed in
   `GOLDEN_RECORDERS`, which `devtools/check_goldens.py` enforces.

**Tests that guard the rules this work keeps.**

- A checkout whose page loads and whose Pulls tab is never opened makes no `gh` call and
  loads nothing beyond `_ROUTE_TABLE_ONLY`. The fake `gh`’s log is the evidence.
- Listing succeeds for a source directory with no store.
  This is the independent evidence that listing touches no Git.
- The full flow on a checkout leaves its `.git` directory byte-for-byte unchanged, and
  passes with that directory read-only.
- The hostile-content corpus (`tests/fixtures/inert-html-hostile-links.json`) passes on
  pull-request text under both profiles.

### Performance

Comparisons follow the performance loop’s rule,
[Judge a tolerance on back-to-back pairs](../../../../explorations/performance-loop/README.md#comparing-a-candidate-with-the-previous-release):
each candidate run is divided by the control run taken next to it, on a quiet machine,
and the careful tolerance is 1.1x. The rough cut’s 1.3x is the loosest tolerance any
comparison here may use, and 2x is never one.

| What | Against | Rule |
| --- | --- | --- |
| A plain folder’s start: imports, startup scripts, first tree | The step’s base, with `startup_pairs.py` and `check_startup_scripts.py` | No new module and no new startup script, which are exact checks; start-up work within 1.1x |
| A checkout’s page load with the tab present and unopened | The step’s base on the same checkout | Within 1.1x; no `gh`, no cache import |
| A mirror’s open with the local prefetch | The step’s base on the same mirror | First tree and the mirror’s own refresh within 1.1x |
| A mirror’s open with the network refresh started at open | The same build with it lazy | Adopted only if first tree and the mirror’s refresh stay within 1.1x; otherwise it stays lazy |
| Opening the tab on a cached list | The spinner delay | Rows painted before `--loading-state-delay`, so no spinner shows; measured in a real browser at one page and at the cap |
| The pull-request page’s open after step 2 | The v0.12 page on the same record | Within 1.1x |
| The list route’s answer at the cap | Its answer at one page | Recorded beside the bound; the parsed list is memoized by file stamp, as `cached_pull_record` does |

Network times of `gh` jobs are recorded for the bounds, not judged by pairs, since they
measure GitHub.

## Delivery

Each step is one pull request against `main`, implemented and reviewed by separate
agents, with `make verify` and green CI, and merged before the next starts.
Each updates [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
and `CHANGELOG.md` in the same change.

| Step | Scope | Checkpoint a person can see | Ships alone |
| --- | --- | --- | --- |
| 1. List data | The model, file, bounds with measurements, the job, both list routes, and the fake `gh` pages | `metab <repo-url> --api '/api/plugin/github/pulls?state=open'` lists pull requests, and again offline | Yes |
| 2. On-demand open | Numbered routes, the provider’s set, the attended pull request, the job bound, the Browse code cases, and View file under any head ref | On a server opened from a repository URL, `/pull/<n>` for any number offers **Fetch** and then shows the page | Yes |
| 3. The tab on a mirror | The panel host, the view and its `/pulls` address, filters, states, keyboard, prefetch, and the sessions | Paste a repository URL, open Pulls, select a pull request, and read it | Needs 1 and 2 |
| 4. The tab and pages on a checkout | Identity, the source without a store, records without a comparison, network on use, and both profiles | Open a checkout, open Pulls, and read a conversation, with nothing written to the repository | Needs 3 |
| 5. Files changed on a checkout | The local comparison and what the page says when commits are missing | Files changed for a pull request whose commits are local | Needs 4 |

**Step 1: list data.**

- *Reviewed:* the bounds against their measurements; honest counts on a moved and an
  incomplete list; that no Git runs; that no file carries a credential; the reader
  rules.
- *Leaves out:* any browser change, and any change to the single-pull routes.

**Step 2: on-demand open.**

- *Reviewed:* that every place in
  [One Pull Request per Server](#one-pull-request-per-server) is changed or deliberately
  kept; the rule for what starts a fetch, with mutation checks; the job bound; that a
  pull-request URL behaves as before, by the regenerated transcripts’ diff.
- *Leaves out:* the list and the tab.
  Steps 1 and 2 are independent and may be built in either order.

**Step 3: the tab on a mirror.**

- *Reviewed:* the startup budget and import boundary; lazy mounting, replacement, and
  disposal; each `gh` state; keyboard and screen-reader behavior; the prefetch
  measurement and its verdict.
- *Leaves out:* checkouts.
  The tab is registered only when a pin is served.

**Step 4: the tab and pages on a checkout.**

- *Reviewed:* the four tests under [Parity and Tests](#parity-and-tests) that guard the
  rules; the security review of untrusted text in a trusted page; the `unattached` state
  across acquisition, listing, and the cache routes; the fork wording.
- *Leaves out:* Files changed, which shows as unavailable with the reason.

**Step 5: Files changed on a checkout.**

- *Reviewed:* that only reads run in the user’s repository; the base the page names; the
  wording when commits are missing.
- *Leaves out:* the in-page fetch into a mirror, unless the user chooses it in item 4,
  in which case it is a sixth step with its own design review.

## Risks

- **Step 2 touches working v0.12 behavior.** It changes `mirror_refresh.py` and the pull
  routes that the released pull-request page depends on.
  It is isolated in one pull request, and its review reads the transcript diffs.
- **List pages are heavy.** The REST list embeds full repository objects in every item
  and has no field selection.
  If step 1 measures a first page as too slow, the choices are a smaller page or
  GraphQL. GraphQL selects fields and could carry check and review summaries in one
  request, but it needs `POST` in the `gh` runner, a second query surface to validate,
  and a different rate-limit budget.
  Adopting it would change this plan’s list design.
- **Rate limits.** A reader who opens many pull requests spends at least six API
  requests on each. The job bound, the per-number window, and waiting for `reset_at`
  limit it.
- **No second line of defense on a checkout.** The alternative to relying on the inert
  layers alone is to load every pull-request page on a trusted folder as its own
  document under the untrusted policy.
  That costs a full page load per pull request and gives up the in-place open.
  It is adopted if step 4’s security review asks for it.
- **Identity on a checkout is read by looser rules than the plugin’s**, and from a
  `.git` that Git itself might refuse, such as one owned by another user.
  It is used only to name a repository in a `GET` to GitHub after the user opens the
  tab, and it is validated again by the plugin’s grammar.
- **A fork’s list may be empty**, which can read as a fault.
  The tab names the repository it lists.
- **The cache grows.** Each opened pull request adds a record, bounded by
  `MAX_PULL_RECORD_BYTES`, and on a mirror its commits.
  Nothing deletes either in the first version; cache management (`mb-0ybg`) owns that.
- **Two servers can refresh one repository’s records at once**, a checkout’s and a
  mirror’s. Writes are atomic replacements, so the later one wins and neither file is
  torn.
- **`gh` changes its text.** The runner classifies some failures by `gh`’s messages,
  recorded from one version.
  A changed message degrades to `gh_failed`, which the tab shows with **Retry**.

What would change the plan: any decision below; a measurement that fails its rule in
[Performance](#performance); a second hosting provider, which would test whether the
shell’s host is as neutral as intended; and demand from an external plugin for
navigation panels, which would reopen the public SDK question the thin-mirror plan
closed.

## Open Decisions for the User

Each has a recommended default, which the plan above assumes.

1. **Which remote identifies the repository on a fork.**
   - *Recommended:* `origin`, with the tab naming the repository it lists.
     It is what the page already uses to open GitHub links locally, so a page has one
     identity.
   - *Alternatives:* the repository `gh` itself would pick, which `gh repo set-default`
     records in the checkout’s Git configuration and which is confirmed against the `gh`
     in use before anything relies on it; `upstream` when present; or a selector in the
     tab.
   - *Affects:* which list a fork’s owner sees first.
     Records are keyed by repository, so changing the rule later migrates nothing.

2. **Row content.**
   - *Recommended:* number, title, state, author, updated time, head and base names, and
     label names. No check or review summary.
   - *Cost of the summary:* three more requests per row on every refresh (check runs,
     the combined status, and reviews), so 300 for a page of 100 against one.
     GitHub allows an authenticated user 5,000 requests an hour
     ([rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)),
     so sixteen such refreshes in an hour would use it up.
   - *Affects:* refresh cost and time, and whether GraphQL is needed.

3. **Whether a checkout’s tab makes network requests only on the user’s action.**
   - *Recommended:* yes. Nothing at startup; the list loads when the tab is opened and
     refreshes in the background only while the tab is shown.
   - *Affects:* the first open of the tab on a checkout waits for GitHub once.
     After that the cached list shows at once.

4. **Files changed on a checkout when the commits are missing.**
   - *Recommended:* say so and give the two commands, with no fetch of any kind.
     Opening the pull request from a mirror gives the whole page, including code at its
     head, which a checkout’s server cannot show.
   - *Alternative:* the in-page fetch into Metabrowser’s mirror, as a sixth step.
   - *Affects:* whether a folder’s server ever clones, and one more step.

5. **Whether closed pull requests are listed by default.**
   - *Recommended:* no. Open is the default filter, as on GitHub; Closed and All are
     fetched when chosen.
   - *Affects:* requests per open, and the cache’s size on a repository with a long
     history.

6. **How many pull requests are kept per repository.**
   - *Recommended:* for a list, the first page of a state automatically and more on the
     reader’s **Load more**, up to a measured cap whose starting hypothesis is ten pages
     per state. For records and fetched heads, every pull request the reader opened, with
     no deletion in the first version, as for Git objects.
   - *Affects:* disk, the time of a full list refresh, and how far back the tab reaches
     before it sends the reader to GitHub.

## Decisions Already Made

By the user, in their words where quoted.

**2026-10-01**

- “when I open a repo can I get a list of all the PRs?
  could Pulls be a new tab alongside the git tab?”
  The list is a Pulls tab beside Git.
- “when you open a github repo that would automatically appear, if we know we have the
  right setup.” The tab appears by itself for a GitHub repository, and the state of `gh`
  is shown in it.
- “we also need to consider how to offer that (having views and refreshing on the github
  PRs and other data) on top of an existing checkout as well as a metabrowser-owned
  cache checkout.” Checkouts are in scope.
- “we can land the stack first then continue a new stack with the pulls tab”, and “let’s
  stabilize everything else but not implement the pulls tab yet, just make sure we’ve
  planned it well.” This plan is written now, and the work starts after the v0.12 stack
  lands.

**2026-09-23**, from the thin-mirror plan’s
[Decisions](plan-2026-09-23-v012-thin-mirror.md#decisions-2026-09-23-by-the-user)

- Metabrowser is as thin a wrapper as possible over `git` and `gh`.
- The cache is a plain mirror.
- Authentication is external: `gh`.
- github.com only.
- GitHub support is internal, with no new public SDK.
- Browsing should feel like the GitHub web interface, served from a seamless cache:
  “instant from the mirror, refreshed in the background”.

**2026-08-15**, a product principle, recorded as principle 6 of the
[design system](../../../design-system.md#principles)

- “effortlessly fast: prefetch by default, never flash a spinner under ~50ms”.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
