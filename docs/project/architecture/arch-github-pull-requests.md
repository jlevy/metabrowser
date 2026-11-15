# GitHub Pull Requests

**Status:** Built: the GitHub provider (URL reducer, `gh` runner, and rate-budget
governor), pull-request records with their commits fetched into the store, the
repository catalog and its search, lightweight cores, changed-file lists, checks in the
record, the Conversation timeline, native stack metadata, revision snapshots, rendered
Markdown diffs, background prefetch, and pull requests beside a served checkout.
Not built: opening a timeline commit in Metabrowser rather than on GitHub, and hosted
releases and other providers, which the
[GitHub provider plan](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md)
leaves to later work.

GitHub support is the built-in `github` plugin under `builtin_plugins/github/`. It keeps
a pull request’s **data**, which `gh api` reads into files beside the source, apart from
its **commits**, which Git fetches into the repository store, so a page reads both
offline and neither waits on the network.
The store, its layout, and its locks are in
[Repository Cache](arch-repository-cache.md); fetching and refresh cadence are in
[Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md); the comparison
service the Changes tab uses is in [Diff Pipeline](arch-diff-pipeline.md).
The designs come from the
[Pulls tab plan](../specs/active/plan-2026-10-01-github-pulls-tab.md) and the
[pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md);
what a reader does with them is in
[Reviewing Pull Requests](../../reviewing-pull-requests.md).

## The Provider Boundary

Core names no provider.
It asks the providers `cache/providers.py` lists, through `RepositoryProvider`, for six
things: URL reducers, Git configuration for a remote (the credential helper), a check
before a first clone, a mirror’s `repository_context`, the commit a pull-request URL
pins, and the set of pull requests a server keeps fresh.
`GithubProvider` in `provider.py` answers all six.
The URL reducer in `urls.py` claims github.com and raw.githubusercontent.com; its
docstring tabulates every URL shape it accepts and what each selects.

`gh.py` is the only way the plugin reaches GitHub.
`gh` owns authentication, and Metabrowser never reads, stores, or logs a token.
Every run has no stdin, prompts and update checks off, the `GH_*` variables that would
redirect it cleared, a deadline and an output cap (`GH_API_TIMEOUT_S`,
`GH_API_MAX_BYTES`), and its own process group, registered with Git’s so a Ctrl-C or
hangup kills it too.
`gh_api` issues one REST request and returns status, headers, and body; `gh_graphql`
runs only a read-only query document, checked by its structure; `gh_account` reads the
active login.
Nothing there paginates or caches, because `--paginate` and `--cache` would
hide page caps, ETags, and rate-limit headers.
`gh api` refuses every request while signed out, so every record is read by an account
and names its reader as `gh:<login>`.

`gh_budget.py` keeps, per process, the newest `x-ratelimit-*` observation of each
resource every response carries, and holds every resource after a `rate_limited` refusal
until its `reset_at`. Background work is admitted only while each resource it spends has
more than `BACKGROUND_FLOOR` of its limit left and no hold applies; a reader’s own work
is never asked. The observations belong to the account the last account check named, and
another account forgets them; since `remaining` is the account’s, several servers on one
account stop together.

## Files Beside a Source

Every file is disposable: a Pydantic model with its own bounds and schema version, read
with a size bound and written atomically by the home’s private file writer under the
source-alias lock. A file another schema wrote is fetched again, never migrated.

| File | Holds | Module |
| --- | --- | --- |
| `sources/<slug>/pulls/<n>.json` | The pull-request record | `pull_record.py` |
| `<n>.refresh.json` | How its last refresh ended | `pull_record.py` |
| `<n>.core.json`, `cores.refresh.json` | Its lightweight core, and the repository’s core holds | `pull_core_cache.py` |
| `<n>.files.json`, `<n>.files.refresh.json` | Its changed files, and how their refresh ended | `pull_list.py` |
| `<n>.snapshots.json` | Earlier comparison pairs a revision link may open | `pull_snapshot_cache.py` |
| `<n>.timeline.json` | The Conversation timeline projection | `pull_timeline.py` |
| `catalog.sqlite3`, `list-<filter>.refresh.json` | The repository catalog, and how its refreshes ended | `pull_catalog.py`, `pull_list.py` |
| `stacks.json` | The native stack snapshot | `pull_stacks.py` |
| `repository-stores/<store key>/github-pull-manifests/`, `github-pull-manifest-<slot>.epoch` | Prepared comparison manifests, and each slot’s epoch | `pull_manifest.py` |

`cache/paths.py` spells the source-side names.

## Pull-Request Records

`refresh_pull_request` in `pulls.py` is the whole network job for one pull request: the
account, then the pull request, its issue comments, reviews, review comments, and the
head’s check runs and combined status, a page at a time with `If-None-Match` from the
same reader’s previous record; the account again, discarding a record read across an
account switch; then the head fetch and the comparison endpoints; then the record.
A part GitHub refuses, such as check runs, and a comparison whose base cannot be
fetched, are named in the record’s `unavailable` rather than failing it.

`pull_record.py` holds `PullRecord` and every bound, with the measurements beside the
constants. A page larger than `gh`’s output cap is asked for again in smaller pages; an
item still too large is left out and its list marked incomplete; every text is budgeted
on its JSON-escaped size, so a written record always fits `MAX_PULL_RECORD_BYTES`.
`record_revision` is a SHA-256 digest of the record without `fetched_at` and the ETags,
so it tells changed content apart even when two refreshes share a timestamp.

The commits come through `cache/pull_refs.py`, which fetches the origin’s
`refs/pull/<n>/head` into the same ref in the store, the one ref a store holds beyond
the origin’s branches and tags, so a fork’s commits arrive with it:

- An open pull request’s base branch is fetched in the same command into
  `refs/remotes/origin/<base>`, so the merge base is taken against the base as it is
  now, as GitHub computes Files changed.
  A closed or merged one compares from the API’s `base.sha`, fetched by ID when no
  mirrored ref reaches it.
- The fetched head must be the head the API reported; one full re-read covers a push in
  between, and a second mismatch is `head_mismatch`.
- Every fetch holds the store’s fetch lock and removes what a killed fetch left first.
  One that finds another refresh holding it tries again every `FETCH_LOCK_RETRY_S` for
  up to `FETCH_LOCK_WAIT_S`, then reports `refreshing_elsewhere`.
- On a case-insensitive file system the base branch is fetched only when the store lists
  it under exactly that name, and the fetch gets the mirror update’s case-fold check.
- Preparing a comparison from a cached record reuses the head already in the store and
  compares from the record’s `base.sha`, recorded as `base_from: base_sha`, without
  fetching the moving base branch; the next refresh compares against the branch again.

Before the record is published, `pull_manifest.py` prepares its comparison manifest in a
disposable bank beside the store: `MANIFEST_SLOTS` direct-mapped slots, each holding a
File Diff Format document without patches and the full build, store, endpoint, and
base-policy identity, so a collision evicts and never answers another comparison.
A slot’s epoch makes old data miss after detected corruption even when the slot itself
cannot be rewritten.
A read-only bank still serves recomputed comparisons.

A mirror’s record write also keeps `<n>.snapshots.json`, the pairs earlier records
named, so a revision link opened at an earlier base and head keeps opening after a
refresh moves the record on.
It holds one reader’s pairs, starts over when another reader writes the record, and
admits each pair only for the store that computed it.

## Serving Pull Requests

A server serves any pull request of its repository.
The provider hands it `ServedPulls` (`served_pull.py`), a `PullRequestSet` that gives a
`ServedPull`, a `CompanionRefresh`, for a number, and keeps the state of at most
`MAX_KEPT_PULLS` in memory, since the numbers are request text.

- **One attended pull request:** the session attends to the one its URL named, replaced
  whenever a pin switch serves another’s head.
  Its record’s age counts toward the mirror’s staleness, so the refreshes that keep a
  served page fresh keep it fresh too.
- **Jobs:** a refresh is a coordinator job under `<store key>:pull/<n>`, so requests
  join it. At most `MAX_PULL_JOBS` may be queued or running, and past it a request is
  refused `too_many`; the attended pull request may run one over.
  Within a server, these jobs and the mirror’s fetch take turns at the store
  (`StoreTurn` in `mirror_refresh.py`).
- **What starts one:** a reader’s own action (`"retry": true`); a visible page whose
  record is stale and not tried within the window; and a
  [prefetch](#background-prefetch) that names it.
  A failed refresh is tried again after a window, and after `rate_limited` not before
  `reset_at`. A branch or tag pin never runs `gh`.
- **One-shot commands:** the CLI fetches a pull request only when it has no usable
  record or its commit URL names a commit only `refs/pull/<n>/head` can bring;
  `--no-serve` refreshes it.
  When a pull request cannot be opened, the CLI answers from a cached record, or falls
  back to the default branch or the commit URL’s commit, and says why.

`pull_route.py` builds the pull envelope from the cache and memory alone; its docstring
lists the states. The envelope’s `pin` is the commit the server serves and can differ
from the record’s head: a pull request opened from the list moves no pin, a commit URL
inside the pull request pins that commit, and a refresh can find a newer head, which the
page offers as `latest` rather than switching under a reader.
**Browse code** is a link to the served root when the pin is the record’s head, and
otherwise a button that posts the head ref to `/api/source/pin` and then opens the root,
so what moves the pin is never a link a modified click could open without moving it; a
checkout has no pin and no Browse code.
Changes never switches the pin, on a mirror or beside a checkout: its file links open
the envelope’s `snapshot_route`.

## Freshness Verdicts

`pull_freshness.py` judges a record and a file list by events rather than the clock.
The catalog’s delta scan reads pull requests by `UPDATED_AT`, and each row carries the
head commit, so a record is checked against its row when the catalog has the record’s
source and reader:

- **changed** when the row is newer, or as new with another head (`head_moved`);
- **current** when the scan that published the row ran within the window, or the next is
  running and the last ran within `SCAN_GRACE_S` past it;
- **checks** for an open record past the window that the catalog still vouches for,
  since `updated_at` does not move for check runs, statuses, or mergeability: its
  refresh reads those alone, with ETags and no fetch into the store; and
- **unverified** otherwise, which the freshness window decides.

`verified_at` and `verified_by` say when and how the record was last known to describe
GitHub. They move with every scan, so the entity tag leaves them out and
`x-metabrowser-verified` carries them.
`checks_pending` reports checks still settling (`NO_CHECKS_GRACE_S`).
`cli-github-pulls-prefetch.txt` pins each verdict.

## The Catalog

`pull_catalog.py` keeps one SQLite catalog per repository of lightweight rows, with a
`(state, number)` index for the Open and Closed windows; merged rows are closed.
Its checkpoint holds the repository identity, the reader, GitHub’s counts, the cached
counts, the scan cursors, freshness, and content generations.
Listing takes a `ListedRepository` and never a store, so a checkout without one has a
catalog.

**Writing.** `pull_list_refresh.py` reads GraphQL pages of at most `PAGE_SIZE` rows
(`pull_catalog.py`), with no description, comment, review, check, or patch: the reader’s
filter prefix first, as far as the reader has scrolled, then the backfill of every pull
request, newest first.
Nothing caps the catalog’s size.
The prefix and the delta scan are the reader’s work; the backfill is background work
that asks the governor before each page and stops at a page boundary when it is held, to
resume from the saved cursor.
Every page query returns `viewer.login`, which must match the job’s reader before any
row is published, and a later page from another account is refused.
A delta scan reads by `UPDATED_AT` through the previous watermark and advances freshness
only when it finishes; a row’s `updated_at` keeps an older backfill page from
overwriting it, and a row absent from an incomplete scan is not inferred deleted.
GraphQL errors, including partial data with HTTP 200, never advance a checkpoint.
Each page commits its rows, counts, and cursor in one short transaction under the
source-alias lock, a checkpoint revision rejects a superseded publisher, and no network
work runs under the lock.

**Admission.** Reads open the database read-only and run neither Git nor `gh`. Readers
and writers admit only the exact tables and index, and refuse a write-ahead-log database
before SQLite opens it.
A catalog a newer release wrote declares it, in `user_version`, the checkpoint’s schema,
or a row’s projection, and is left as it is with the refresh ending `newer_cache`,
because several builds can share one cache.
One whose versions cannot all be read safely ends `unknown_cache`; anything else a
writer cannot use is replaced with an empty catalog under the lock.
The module docstring gives each case, and `tests/test_github_pull_list.py` pins the
shape each version names.

**Reading.** `GET pulls` answers an indexed window of up to `MAX_WINDOW` rows below
`after`, newest first, with GitHub’s counts dated by `count_at` beside the cached ones.
A per-filter `generation` changes when existing content or the leading prefix changes,
not when older pages are appended, so a client replaces a held window only after
collecting one under a single source, reader, and generation.
With `q`, the same route is Quick Search’s completion list across every state
(`catalog_search`): a number uses the number index, `#` alone lists the newest, and text
scans titles within `_SEARCH_TITLE_ROWS` and an instruction budget, saying `limited`
when it stopped there.

## Lightweight Cores

A **core** is a pull request’s validated header and description, prepared ahead of
selection so a row shows its description before the full record exists.
`pull_core_cache.py` stores each in `<n>.core.json`, bound to the source, repository,
reader, catalog epoch, and the row’s summary fingerprint.
An ordinary catalog refresh keeps its epoch, so unchanged cores stay usable after the
freshness window and across restarts; a changed fingerprint lets the older core show,
marked stale, while preparation fetches the update; a changed account, repository, or
epoch refuses it. A complete record always takes precedence.

`POST pull-cores-prepare` (`pull_cores.py`) takes a window identity and a batch of at
most `MAX_CATALOG_MEMBERS` numbers, admitted against the exact catalog generation, and
answers one of the `Preparation` outcomes.
A ready answer lists `ready_numbers` and `skipped_numbers`, a partial one adds
`retry_numbers` and `retry_at`, and the lists account for every member requested.
A source runs one core job at a time; a `visible` batch preempts a `background` one that
reads none of the members it still needs, revoking its window, cancelling its job, and
waiting for it to unwind.
A failed batch holds later ones with the same outcome until another attempt is eligible,
and `cores.refresh.json` keeps provider holds across restarts.
The panel’s batch timeouts are `CORE_VISIBLE_TIMEOUT_MS` and
`CORE_BACKGROUND_TIMEOUT_MS` in `pulls-panel.js`.

A reader who selects a pull request with no record may ask the refresh to wait for its
core (`"wait_core": true`, at most `CORE_WAIT_TIMEOUT_S`); the envelope then carries a
`core_preview` until the full record lands.
A page can ask `GET pull` to wait for that exact preview’s completion
(`wait_full_after`, at most `FULL_WAIT_TIMEOUT_S`), which holds no network slot and
starts nothing.

## Changed Files

`refresh_pull_files` in `pull_files_refresh.py` has two sources for one list:

- **The local comparison:** when the store holds both of the record’s comparison
  commits, the list is that manifest’s, from `git diff --raw` and `--numstat`, with no
  patch and no network.
- **GitHub’s list:** otherwise, or when the manifest is cut at `MAX_MANIFEST_FILES`
  (`diff/adapters/git.py`) or Git cannot list it, as when the lender has gone or
  collected the head, one `gh api …/pulls/<n>/files` page at a time, up to GitHub’s own
  cap (`MAX_PULL_FILES`). It runs no Git, and `tests/test_github_pull_files.py` proves
  it with a failing `git` first on `PATH`.

GitHub’s list is published after every page that leaves it holding more rows than the
file does, as `complete: false`, so a first list arrives page by page and a held list
never shrinks while it is read again.
The account is checked before each publication; a change stops the job as
`account_changed`, and earlier prefixes stay readable, marked stale.
Every list carries a `generation`, minted once per refresh and shared by its
publications, which tells a replacement from an appended page.
The job runs under `<slug>:pull/<n>/files`, takes no turn at the store, and holds a
network slot only for each `gh` request.

`pull_files_route.py` answers from the cache alone; its docstring states the freshness
rule. A local list is current while the record names its exact comparison; a GitHub list
while the head and base branch it was read for are the newest known.
When source admission refuses the cache, no stamp can be written, so the outcome
`cache_unwritable` is kept in bounded memory and holds automatic retries without
contacting GitHub or touching the refused cache; it does not survive a restart.

## Comparisons

**Merge bases on a shallow store.** `merge-base` on a cut graph can name a common
ancestor that is not the best one, with no error.
`git/shallow.py` believes an answer only when it is certain, and its docstring holds the
proof; an empty answer on a shallow store is uncertain, not `no_merge_base`. When
uncertain, the refresh writes the record with `unavailable.comparison: base_uncertain`
and no comparison, then `deepen_until_certain` in `cache/pull_refs.py` fetches more
history of the base and the head into the store, never the checkout, in the rounds
`DEEPEN_ROUNDS` lists, within the acquisition deadline, and writes the record again if
that settles it. `no_merge_base` is only Git’s own answer that two commits share no
history; a commit the walk could not read is `commits_unavailable`. A commit at the
boundary is grafted into a root, so its diff answers `parent_unavailable` rather than
showing a whole tree as added.

**Routes.** `GET pull-comparison` names a cached pull request and two full commit IDs
with `merge_base`, reads only the selected store, never fetches, and forwards to the
diff plugin’s comparison service with the prepared manifest, hydrating
`INITIAL_PULL_FILES` files in its first answer.
`GET pull-snapshot` (`pull_snapshot.py`) opens a file at the exact displayed base or
head without changing the pin or the checkout, for a pair the record or its snapshot
file admits; its docstring lists every outcome code.
`GET pull-rendered-diff` (`pull_rendered_diff.py`) answers one changed Markdown file as
`markdown-diff-v1` after the same admission, computed in a projection worker process.
`GET pull-markdown` (`pull_markdown.py`) renders one text of the record through KPress
in sanitized mode, then reduces it to the inert allowlist of `inert_html.py`; only
KPress’s stylesheet manifest reaches the page, so no text chooses what loads.
The trust model behind that allowlist is in
[Server and Content](arch-server-and-content.md).

## Conversation Timeline

`POST pull-timeline` (`pull_timeline.py`) gives Conversation the order of commits,
comments, and reviews from GitHub’s timeline connection, for a record revision the page
names. It reads at most `MAX_PAGES` pages of `PAGE_SIZE` events and keeps the projection
in `<n>.timeline.json`, bound to the inputs it orders (`_discussion_revision`): the
source, number, reader, base branch, head, and the discussion’s identifiers.
An advance of the base branch keeps it usable; a retarget or a new head needs a new one.
It answers `complete`, `partial` with a retryable verified prefix, or `unavailable`,
asks for no patch or Git object, and runs only after the selected Conversation paints,
in a provider slot of its own once any metadata refresh settles.

## Native Stacks

`pull_stacks.py` keeps one optional `stacks.json` per repository, apart from the catalog
and records: native stack numbers, which are labels and not pull-request numbers, with
their ordered bottom-to-top members.
A coordinator job probes `gh stack --version` from an isolated directory, then reads
GitHub’s REST stack pages; it never runs `gh stack view`, checkout, sync, or tracking
commands.
REST pages name no reader, so the job checks the account before and after them.
The snapshot’s bounds (`MAX_STACK_PAGES`, `MAX_STACK_MEMBERS`, `MAX_SNAPSHOT_MEMBERS`,
`MAX_STACK_BYTES`) are measured beside them; a page that would exceed them is omitted
and the snapshot marked incomplete.
Membership missing from a partial or unavailable snapshot never means a pull request is
unstacked, and `403` or `404` is neutral unavailability.
Attempts wait `STACK_FRESHNESS_S`, and a failure keeps the preceding snapshot.

## Background Prefetch

A visible page names what the reader is likely to open next with `POST pulls-prefetch`
(`pull_prefetch.py`); nothing on the server starts that work by itself, so a hidden or
offline page spends nothing.
The request names records and changed-file lists, each at most `MAX_PREFETCH_NUMBERS`
numbers in priority order, and replaces the repository’s lane queue.
The lane is one coordinator job per served repository that runs one item at a time,
alternating records and file lists, rereads each from disk before it runs, and stops
when the governor refuses.
Its caps (`RECORDS_PER_SCAN`, `RECORDS_PER_HOUR`, `FILES_PER_HOUR`) and the GitHub
points they cost are worked out in the module docstring.
A background job takes no network slot, waits at a store turn behind every other job and
is cancelled when one starts waiting, and a reader’s request for the same pull request
joins and promotes it.
`GET pulls-prefetch` reports the lane, the caps, the governor, and the last `MAX_RECENT`
outcomes from memory.
The panel’s choice of what to name, and when (`FILES_DWELL_MS`), is in `pulls-panel.js`.

## Beside a Checkout

A folder server has no mirror session, so `checkout.py` says which repository its pull
requests are of: the served checkout’s `origin`, read from files with no Git process,
reduced through the GitHub grammar and lowercased, so an HTTPS remote, an SSH remote,
and a mirror of one repository share one identity and one set of records.
A subdirectory resolves to its enclosing checkout.
Reading creates nothing, and a job’s first write publishes an `unattached` source with
no store.

- **Comparisons need a store.** Without one, the envelope withholds a record’s
  comparison as `no_store`. Opening **Changes** sends
  `"retry": true, "comparison": true`, which acquires an overlay with the checkout as
  lender
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout))
  or reuses a healthy store, and leaves the served folder and its Commits tab unchanged.
  It first waits out another process’s cold open of the source.
- **Idle preparation:** once a store is attached, a visible Conversation can ask for a
  current record’s comparison as optional work (`"prepare_comparison"` with the record
  revision). It fetches only that pull request’s head and base, never deepens, holds no
  network slot, and records no outcome; a reader’s Changes request promotes it, and
  another pull request’s refresh cancels it.
- **Repair:** Changes offers Refresh for a displayed comparison even while the record is
  fresh. The request carries `"recovery": {"base": …, "head": …}`, which the server
  accepts only for a pair this session issued for that pull request (the last
  `MAX_ISSUED_COMPARISONS`), then runs the
  [object recovery](arch-mirror-acquisition-and-refresh.md#object-recovery).
  A successful repair remounts the same comparison once, and a failed one leaves it in
  place.

`GET` routes never acquire or fetch.
What a reader sees for each failure name, and what to do, is in
[Reviewing Pull Requests](../../reviewing-pull-requests.md).

## Clearing the Cache

`POST cache-clear` takes an empty object and removes every entry of the source’s `pulls`
directory (`clear_pulls` in `pull_record.py`), under the source-alias lock every writer
of those files takes; each is fetched again when next wanted.
The source’s own records, its store, and the store’s manifest bank stay.
The `cache_unwritable`, `newer_cache`, and `unknown_cache` messages name it as the
command to paste (`cache_clear_command` in `gh_lists.py`).

## Routes

Every route is under `/api/plugin/github/`, a `[[data_hook]]` of the plugin’s
`manifest.toml`. A `GET` answers from the cache and memory alone and runs no `gh`; a
`POST` takes a JSON body, which keeps a link in untrusted content from reaching it, and
one that starts a refresh job returns `202` at once and names a `status_route`. Each
handler’s docstring in `sidekick.py`, or the module it names, holds its contract.
`tests/test_github_route_table.py` checks this table against the manifest, and the
parity table in [Views, Models, and Routes](arch-views-models-routes.md) names each
route’s golden.

| Route | Methods | Answers or starts |
| --- | --- | --- |
| `pull` | `GET` | One pull request’s envelope |
| `pull-refresh` | `POST` | That pull request’s refresh, comparison, repair, or idle preparation |
| `pull-cores-prepare` | `POST` | A batch of lightweight cores |
| `pull-comparison` | `GET` | The record’s comparison, from the store |
| `pull-snapshot` | `GET` | A file at the comparison’s base or head |
| `pull-rendered-diff` | `GET` | One changed Markdown file, rendered |
| `pull-timeline` | `POST` | Conversation’s order of commits, comments, and reviews |
| `pull-markdown` | `GET` | One text of the record, rendered inert |
| `pulls` | `GET` | A catalog window, or a search with `q` |
| `pulls-refresh` | `POST` | The catalog job |
| `pull-files` | `GET` | A pull request’s changed files |
| `pull-files-refresh` | `POST` | That list’s refresh |
| `stacks` | `GET` | The native stack snapshot |
| `stacks-refresh` | `POST` | The stack job |
| `pulls-prefetch` | `GET`, `POST` | The background lane’s report, or a new queue for it |
| `cache-clear` | `POST` | Removal of the plugin’s records for the repository |

The plugin registers two views: `pull-request`, which the shell mounts at `/pull/<n>`,
`/pull/<n>/files`, and `/pull/<n>/checks` (`pull-page.js`), and `pull-request-list`, the
Pulls tab and `/pulls` (`pulls-panel.js`). Their visual rules are in the
[design system](../../design-system.md#the-pulls-tab).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
