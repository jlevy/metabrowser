# GitHub Pull Requests

**Status:** Built: the GitHub provider (URL reducer, `gh` runner, and rate-budget
governor), pull-request records with their commits fetched into the store, the
repository catalog and its search, lightweight cores, changed-file lists, checks in the
record, the Conversation timeline, native stack metadata, the repository’s label set,
revision snapshots, rendered Markdown diffs, background prefetch, the page’s comparison
keep, and pull requests beside a served checkout.
Not built: opening a timeline commit in Metabrowser rather than on GitHub, and hosted
releases and other providers, which the
[GitHub provider plan](../specs/done/plan-2026-08-27-github-provider-and-pull-requests.md)
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
[Pulls tab plan](../specs/done/plan-2026-10-01-github-pulls-tab.md) and the
[pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md);
what a reader does with them is in
[Reviewing Pull Requests](../../reviewing-pull-requests.md).

## The Provider Boundary

Core names no provider.
It asks the providers `cache/providers.py` lists, through `RepositoryProvider`, for: URL
reducers, Git configuration for a remote (the credential helper), what to say when a
source was not found or needs credentials (`credential_hint`), a check before a first
clone, a mirror’s `repository_context`, the commit a pull-request URL pins, the changed
file a Changes tab URL’s anchor names (`pull_request_file`), the set of pull requests a
server keeps fresh, and the pull requests a branch is the head of, from the cache alone
(`ref_pulls`, [By head branch](#the-catalog)). `GithubProvider` in `provider.py` answers
each. `provider_statuses` in the same module collects each provider’s section of
`metab --doctor`, and `PullRequestUnavailableError.blocking` tells the command line that
a pull request can open only once a tool is installed or signed in, without naming the
tool; both come from [the GitHub status check](#the-github-status-check).
The URL reducer in `urls.py` claims github.com and raw.githubusercontent.com; its
docstring tabulates every URL shape it accepts and what each selects.
GitHub’s `#diff-<hash>` anchor, on a `/pull/<n>/files` or `/pull/<n>/changes` URL, is
the SHA-256 of a changed file’s path, so `pull_file_anchor.py` names the file from the
cached list of changed files and then the record’s comparison, offline, and the URL
opens at `/pull/<n>/files/<path>`, or at the Changes tab with the reason when neither
names one or the Changes tab has no address for its path.

`gh.py` is the only way the plugin reaches GitHub.
`gh` owns authentication, and Metabrowser never reads, stores, or logs a token.
Every run has no stdin, prompts and update checks off, the `GH_*` variables that would
redirect it cleared, a deadline and an output cap (`GH_API_TIMEOUT_S`,
`GH_API_MAX_BYTES`), and its own process group, registered with Git’s so a Ctrl-C or
hangup kills it too.
`gh_api` issues one REST request and returns status, headers, and body; `gh_graphql`
runs only a read-only query document, checked by its structure; `gh_active_account`
reads the active account, its token source, and its scopes, and `gh_version` the
version.
Nothing there paginates or caches, because `--paginate` and `--cache` would hide
page caps, ETags, and rate-limit headers.
`gh api` refuses every request while signed out, so every record is read by an account
and names its reader as `gh:<login>`.

`gh_budget.py` keeps, per process, the newest `x-ratelimit-*` observation of each
resource every response carries, and holds every resource after a `rate_limited` refusal
until its `reset_at`. Background work is admitted only while each resource it spends has
more than `BACKGROUND_FLOOR` of its limit left and no hold applies; a reader’s own work
is never asked. The observations belong to the account the last account check named, and
another account forgets them; since `remaining` is the account’s, several servers on one
account stop together.

### The GitHub Status Check

`gh_status.py` answers what GitHub work needs from `gh`: its path and version, the
active account, the account’s token scopes, and one state with the step that fixes it.
Its docstring tabulates the states.
The step is `fix`, a command, page, or sentence for the text output, and `remedy`, the
same step in the doctor checks’ `{text, command, url}` shape, which names a command only
for one that runs as written, so a reader never parses `fix`. These read it:

- `metab --doctor` prints it after the plugin verdict, and `--doctor --json` carries it
  as `github`. It never changes the exit status, since a machine without `gh` has
  nothing wrong with its plugins.
- `POST status` serves the same object, a `POST` because it runs `gh`; `{"fresh": true}`
  asks `gh` again rather than reuse a recent answer or join a check already running.
- `check_first_clone` reads it before the size check, without the version.
  A pull-request URL stops before anything is cloned when the state is `gh_missing`,
  `gh_too_old`, or `not_logged_in` (`SIGN_IN_STATES`), since only `gh` reads a pull
  request; a repository URL goes on, since a public one clones anonymously.
  The size check is skipped only for `gh_missing`, `not_logged_in`, and `network_error`,
  where its read cannot succeed; a `gh` too old for the status check may still read the
  size. A clone that then fails as not found takes its hint from the kept answer
  (`credential_hint`), so a token without the `repo` scope is named.
- `GithubProvider.pull_request` asks it when GitHub does not show a pull request, which
  on a cached mirror no first-clone check preceded, and names a missing `repo` scope.

A pull request with no usable cached record whose read fails in one of those states also
stops the command, with `PullRequestUnavailableError.blocking`, rather than fall back to
the default branch, since the fallback would show something other than what the URL
asked for. A page already open shows the reason and offers **Fetch**, as for any other.

The answer is kept for `GH_STATUS_TTL_S` per `gh` path and configuration, and callers in
one event loop share a check in flight; `GH_STATUS_TIMEOUT_S` bounds a `gh` that hangs.
A token GitHub refuses in `GH_TOKEN` or `GITHUB_TOKEN` is `not_logged_in` with a fix
that names the variable, since `gh auth login` refuses to run while it is set.
A token whose scopes `gh` does not report, such as a fine-grained one from `GH_TOKEN`,
is `ok`, since only a repository’s own read can tell what it reaches.

## Files Beside a Source

Every file is disposable and carries its own schema version.

- **The JSON files** are Pydantic models with their own bounds, read with a size bound
  and written atomically by the home’s private file writer under the source-alias lock.
  A file another schema wrote is fetched again, never migrated.
- **The catalog** is a SQLite database: a page’s rows, counts, and resume cursor commit
  together under the same lock, and `pull_catalog.py`’s docstring says when a catalog
  this release cannot use is replaced.
- **The prepared manifests** beside a store are written atomically without a lock: each
  pull request has one, so a comparison of it at another pair replaces it and costs only
  a later miss (`pull_manifest.py`).

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
| `repos/<store key>/github-pull-manifests/pull-<n>.json`, `github-pull-manifest-<slot>.epoch` | Each pull request’s prepared comparison manifest, and the epochs, direct-mapped by comparison | `pull_manifest.py` |

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
disposable bank beside the store, one manifest for each pull request, so preparing one
replaces no other’s. Each is a File Diff Format document without patches and the full
identity: the document’s schema, the listing (`MANIFEST_LISTING` in
`diff/adapters/git.py`), how the store’s Git is run, the store, both endpoints, and the
base policy, so a comparison of the pull request at another pair replaces it and never
answers for it. The bank holds one for each pull request ever prepared, about a third of
a record each, and clearing the cache leaves it; the measurement is in
`pull_manifest.py`. The identity names no build, so a manifest outlives an upgrade and
an edit of the source.
A change to the listing’s options or to the store read’s isolation moves it, and so does
raising `MANIFEST_READING`, which a change to how a listing is read must do (a test pins
it). An epoch, direct-mapped by comparison (`EPOCH_SLOTS`), makes old data miss after
detected corruption for every pull request that keeps that comparison, even when its
manifest cannot be rewritten.
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
  record is stale and not tried within the window; a probe that finds a change; a
  visible record read `FULL_REFRESH_S` ago; and a [prefetch](#background-prefetch) that
  names it. A failed refresh is tried again after a window, and after `rate_limited` not
  before `reset_at`. A branch or tag pin never runs `gh`.
- **Probes:** a visible page asks every `probe_every_s` (`ATTENDED_PROBE_S`), and for a
  current record the server answers with a probe (`ServedPull.probe`), a conditional
  read of the pull request that GitHub answers `304` without spending its rate limit,
  and, while checks are pending, of their first pages every `CHECKS_PROBE_S`. An
  unchanged probe vouches for the record (`verified_by: "probe"`) and keeps it current
  until the full read `FULL_REFRESH_S` asks; a change starts a refresh at once, a change
  to checks alone reads only them, and a failed probe waits a window.
  Two pages share one probe, and a rate-limit hold stops them all.
  The
  [update cadence plan](../specs/active/plan-2026-11-22-pull-request-update-cadence.md)
  records the measurements and the design.
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
otherwise a button that posts the head’s commit to `/api/source/pin`, naming the pull
request’s `refs/pull/<n>/head` as the ref to serve it under, and then opens the root, so
what moves the pin is never a link a modified click could open without moving it; a
checkout has no pin and no Browse code.
**View on branch** is Browse code for one file, on each file bar of Changes while the
diff shows the pull request’s head: a link to the file’s `/view/` address when the pin
is the head, otherwise a button that serves the head the same way first, and, beside a
checkout whose `HEAD` is the head, a link to the working-tree file.
For a checkout, [Open Modes](arch-open-modes.md#pull-requests-in-a-repository-folder)
designs both controls going to the head as a revision view in the repository folder,
with the working-tree copy a separate, labelled action; that is not built.
The page’s one switch (`createPinSwitch` in the diff plugin) serves both, so a refusal
reads the same from either.
The pin is server-wide, so a switch from Changes moves every tab’s pin, as Browse code
always has; how the other tabs learn it is in
[Source Sessions and Pins](arch-source-sessions-and-pins.md).

## Freshness Verdicts

`pull_freshness.py` judges a record and a file list by events rather than the clock.
The catalog’s delta scan reads pull requests by `UPDATED_AT`, and each row carries the
head commit, so a record checked against its row is **changed** when the row is newer or
names another head, **current** while the scan that published the row is recent,
**checks** when an open record is past the window that its row still vouches for, since
`updated_at` does not move for check runs, statuses, or mergeability, and **unverified**
otherwise; the module docstring states each rule.
`verified_at` and `verified_by` say when and how the record was last known to describe
GitHub: by the catalog’s scan, by its own fetch, or by a [probe](#serving-pull-requests)
of the served pull request.
They move with every scan and probe, so the entity tag leaves them out and
`x-metabrowser-verified` carries them.
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

**By head branch.** The ref chooser lists a branch’s pull requests on its row, and its
filter finds a branch by them (`GET /api/source/refs`,
[Source Sessions and Pins](arch-source-sessions-and-pins.md#switching-the-pin-and-the-pin-guard)).
Core asks the provider, through `ref_pulls_for` in `cache/providers.py`, which names no
provider, and `ref_pulls.py` answers from the catalog alone: `catalog_heads` reads the
cached rows whose `head_repository` is the repository itself, a fork’s or a deleted
fork’s never, within the newest `_HEADS_SCAN_ROWS`, and the answer is kept for each
`(epoch, revision)` of the catalog, so a chooser that asks on every keystroke reads no
row. While a job is filling the catalog each page it writes moves the revision, and a
scan holds off the next page’s write, so the answer is read again at most once in
`RESCAN_WHILE_FILLING_S`, and a scan reads its rows inside the transaction and makes
them pull requests after it; the measurements are beside the constants.
A branch several pull requests name lists the open ones first and then the newest first.
The repository’s own are told from a fork’s by the head repository’s name the catalog
recorded, compared, ignoring case, with the name in the served repository’s address, so
a repository renamed or transferred since its rows were cached reads as a fork’s until
the catalog records its new name (`mb-n3hm`: compare the repository’s id).
A catalog not yet cached answers as absent, with whether a job is filling it, which the
chooser asks again while it is; nothing here starts a job or reaches GitHub.
A checkout’s local branches and its `origin/` remote branches are named as the
repository names them.
A checkout served at one of its own revisions is not the folder the plugin resolves, and
has no Pulls tab
([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)),
so its listing has no pull requests.

## Lightweight Cores

A **core** is a pull request’s validated header and description, prepared ahead of
selection so a row shows its description before the full record exists.
`pull_core_cache.py` stores each in `<n>.core.json`, bound to the source, repository,
reader, catalog epoch, and the row’s summary fingerprint: an unchanged core stays usable
across refreshes and restarts, a changed fingerprint shows the older core marked stale
while preparation fetches the update, and a changed account, repository, or epoch
refuses it. A complete record always takes precedence.
`POST pull-cores-prepare` prepares a bounded batch admitted against the exact catalog
generation, one core job per source, a `visible` batch preempting a `background` one;
`pull_cores.py`’s docstring gives its outcomes, retries, and waits.
A reader who selects a pull request with no record may ask its refresh to wait for the
core, and the envelope then carries a `core_preview` until the full record lands.
The page renders the preview’s description through `GET pull-markdown` as it renders the
record’s, so the description shows rendered from its first paint, and the record that
follows with the same text reuses that render.

## Changed Files

`refresh_pull_files` in `pull_files_refresh.py` has two sources for one list:

- **The local comparison:** when the store holds both of a comparison’s commits, the
  record’s or one the prefetch computed from an open pull request’s head and base
  branch, the list is that manifest’s, from `git diff --raw` and `--numstat`, with no
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
rule. A local list from the record is current while the record names its exact
comparison; a GitHub list, or a local list from a head and base branch, while the head
and base branch it was read for are the newest known, and for the local one while the
pull request is open.
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
The page reads it for Changes and for the header’s Diff summary on every tab.
A comparison asked for once is answered from the process’s memory after that, with no
Git process, and its route names the pull request, both commits, the build, and the
store, so its answer is immutable and a browser asks for it no more.
`test_a_repeated_comparison_runs_no_git_and_a_moved_head_is_computed_afresh` in
`tests/test_github_pull_manifests.py` holds both, and that a route naming another head,
as a record whose head moved does, is computed.
In the page, what was read is kept for the document rather than for one page
([The Comparison Keep](#the-comparison-keep)). `GET pull-rendered-diff`
(`pull_rendered_diff.py`) answers one changed Markdown file as `markdown-diff-v1`, and
one changed YAML or JSON file as `structured-diff-v1`, each computed in a projection
worker process, for a pair the record or its snapshot file admits (`pull_snapshot.py`).
Its images load from `GET pull-image`, which serves an image at the head of an admitted
pair without changing the pin or the checkout; its links to a file of the head are that
file’s `/view/` address, the same in every answer, which the page keeps only while its
pin is the head and leaves as plain text otherwise.
`pull_snapshot.py`’s docstring lists every outcome code.
`GET pull-markdown` (`pull_markdown.py`) renders one text of the record, or with no
record cached the core preview’s description, through KPress in sanitized mode, then
reduces it to the inert allowlist of `inert_html.py`, both in the server’s Markdown
child under its deadline, the same child as the projections, which a served page’s first
`GET pull` starts; a text past the deadline answers `422` `render_deadline`, one that
arrives while the child has as many renders as it takes answers `503` `renderer_busy`,
and the page shows its plain text with a line saying why, which it keeps for that text
until the text renders.
The page asks for the description, and for every text within `MARKDOWN_AHEAD`
(`pull-page.js`) of the view, before the frame that first shows it, and until its render
answers shows a placeholder in its place, never its Markdown source.
A text farther off keeps its plain text, which find in page reaches, and is asked for as
it nears the view, so a jump straight to it shows that text until it is asked for.
Only KPress’s stylesheet manifest reaches the page, so no text chooses what loads.
A text whose render keeps a `pre[lang="mermaid"]` is drawn as an image on every page,
through the Markdown plugin’s exported `drawDiagrams` with `isolated: true`
(`drawTextDiagrams` in `pull-page.js`): the page then loads Metabrowser’s own KPress
diagram modules and vendored Mermaid, none of which the text names.
Mermaid lays a diagram out in a document before it becomes an image, and there the
diagram’s own CSS is live: its image shape, a `themeCSS` directive or front matter, a
`fontFamily` directive, a `cursor: url()`, a state diagram’s `classDef`, a class
diagram’s `style`, and a `block-beta` `style` (from the page’s own origin) each loaded
its URL on a page with no policy, as a folder’s page served trusted has.
So a text’s diagrams are laid out in the diagram frame
(`builtin_plugins/markdown/diagram-frame.js`), an `about:srcdoc` frame sandboxed to
scripts and its own origin, whose own Content-Security-Policy admits its entry and the
Mermaid directory as scripts, its stylesheet (`diagram-frame.css`) and inline style, and
`data:` images, and nothing else, under either profile; the page shows the SVG text it
returns as an image.
The stylesheet gives a label the box the app page’s reset gives it, which the frame
needs under `--untrusted`: the frame inherits the page’s policy, which refuses the
`<style>` Mermaid zeroes a label’s margins with.
One frame serves every text on the page, opened with the first diagram and removed with
the last binding; if it goes any other way, taken out of the page or navigated away, a
render in flight fails rather than holding KPress’s page-wide queue of Mermaid calls,
and the next render opens a new frame.
A diagram drawn around an image, Mermaid’s image shape, cannot get it, so it shows its
source with a message that images in diagrams from untrusted text are not loaded.
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
A coordinator job probes `gh stack --version` from an isolated directory and reads
GitHub’s REST stack pages, checking the account before and after them, since the pages
name no reader; it never runs `gh stack view` or a checkout, sync, or tracking command.
The snapshot is bounded, a page past its bounds is omitted and marks it incomplete, and
membership missing from a partial or unavailable snapshot never means a pull request is
unstacked. A failure keeps the preceding snapshot.

## Stack Change Lines

A stack’s heading in the Pulls tab says the stack’s change as a brief change line
(`stack-lines.js`), which `GET stack-change?number=<stack>` answers
(`pull_stack_change.py`). A stack is the accumulation of its pull requests, merged or
open, so its change is theirs: each member’s cached list of changed files, the one
`GET pull-files` serves, folded in bottom first, one list at a time, through
`pull_change_sums.py`. A file counts once, followed across a rename, with a status
composed from what the members did to it, and every member’s lines are summed.
The route never asks GitHub, fetches, or runs Git.
It keeps the accumulation by each list file’s inode, modification time, and size, so a
repeat stats the lists and parses none, and refuses before reading lists that together
pass `MAX_STACK_LIST_BYTES`.

The envelope has `state` (`current` or `absent`), `reason` (`not_github`, `not_stacked`,
`not_cached` for a member whose list is missing or still filling, or `too_large` for a
list that stops short or lists past the bound), `number`, `pulls`, the members
accumulated, `pending`, `revision`, a digest of the answer’s content, `files`,
`additions`, `deletions`, `exact`, and `statuses`, each a pull request’s status word and
its count. `pending` names the members not settled: with no whole list, or with one the
files route would refresh, not `current` by its own freshness rule (`list_settled`), so
a list from the local comparison waits on the record, as the row’s tree does.
It names nothing but `number`, and its tag is the envelope’s, for a client that holds
one; the Pulls tab sends none, and reads a `304` as its last answer holding.

The answer has no window.
The Pulls tab reads a stack again when its members or a member’s head, as the catalog’s
rows report it, change, a member the list holds no row of taken as unchanged; when the
prefetch lane reports a member’s list refreshed or a row’s own read of its list arrives;
and, silently, while an answer names `pending` members, a minute on and doubling to half
an hour. Its prefetch asks for the members a drawn stack’s answer names, after the
reader’s own rows, in places kept for them (`PREFETCH_STACK_FILES`). The lines count
their reads against a cap of their own, `STACK_LINES_PER_HOUR`, apart from the
comparison warmer’s.

## Row Change Lines

A pull request’s row in the Pulls tab has a third line, its brief change line, which
`GET pull-files-summary?numbers=<n>,<n>,...` answers for every row the list draws in one
request (`pull_files_summary.py`, read by `row-lines.js`). It is what the pull request’s
own cached list of changed files, the one `GET pull-files` serves, sums to, through the
same `pull_change_sums.py` a stack’s line accumulates its members with, so a stack of
one pull request says what its row says: a copied file is `added`, a changed or
unchanged one `modified`, and a file the local comparison has no count for, a binary
file, counts as none and makes `exact` false.
It never asks GitHub, runs no Git, and reads nothing but each list’s file.

The envelope has `source`, null with no `rows` on a server with no GitHub repository,
and `rows` in the request’s order, each with `number`, `state` (`listed` or `absent`),
`reason`, `listing`, `listed_from`, `generation`, `head`, `files`, `additions`,
`deletions`, `exact`, `statuses`, each a status and its count, sorted by the status, and
`size`. The reasons are `not_cached`, `schema_mismatch`, and `unreadable`, no usable
list; `filling`, a list still being read or stopped part-way; `too_large`, a list GitHub
capped or one an item was left out of; and `deferred`, a list past the request’s byte
budget, which a later request reads.
A `filling` or `too_large` answer still names its list’s `listed_from`, `generation`,
and `head`, so a row whose tree reads that same list asks nothing more.
`listing`, read from memory, says the list’s refresh runs in the refresh coordinator or
the prefetch lane holds a files item for it.
A request names `numbers` alone, 1 to `MAX_SUMMARY_NUMBERS` distinct pull-request
numbers; anything else is refused 400 `invalid_request`. One request reads at most
`MAX_SUMMARY_BYTES` of lists it has not summed, the first whatever its size, and a sum
is kept by its file’s inode, modification time, and size, at most `MAX_KEPT_SUMMARIES`
of them, the least recently used out first, so an unchanged list is read once.

`size` is the size the list’s comparison pushes and its patch’s
([Change Sizes](arch-git.md#change-sizes)), when it is kept: in memory or beside the
store, so the route still runs no Git.
The refresh that makes a list from the store measures it right after listing it
(`pull_files_refresh.py`), so a row’s size arrives with its counts; a list GitHub gave
names no merge base and has none.
A pull request’s page asks `GET pull-size` with the envelope’s `size_route`, which names
the record’s comparison as `rendered_route` does and is admitted the same way
(`pull_size.py`); it measures the head against the pair’s merge base once, and keeps it.

## Label Sets

A record carries each label’s color, but a record or a core cached before label colors
names its labels alone.
`pull_labels.py` keeps the repository’s whole label set, one bounded snapshot of
`repos/<owner>/<repo>/labels` in `labels.json` beside the stack snapshot, so such a chip
is colored by name from first paint; it shares its stamps, its hold, and its publish
step with `pull_stacks.py` (`repository_snapshot.py`).

- **Reads never ask GitHub.** `GET labels` reads the cached set with no query
  parameters: `state`, `reason`, `source`, `reader`, `fetched_at`, remaining
  `fresh_for_s`, `refreshing`, `last_refresh`, `complete`, `count`, and `labels`, each
  its `name`, `color` (six lower-case hex digits or null), and `description`, in
  GitHub’s order. `complete` says the last page read named no next page.
  Its tag leaves out the countdown, as the stack snapshot’s does.
- **One start.** `POST labels-refresh` accepts only an optional boolean `retry` and
  returns `refresh`, `labels`, and `status_route`; `202` starts or joins the job and
  `200` is `not_due`. The job runs under its own key, never inside the catalog’s or a
  reader’s job, takes the network slot one page at a time, and asks GitHub only when the
  set is absent, past its age (`LABEL_FRESHNESS_S`), or `retry` asks.
  Nothing in the catalog’s refresh waits on it, and a failure keeps the preceding set.
- **Who asks.** A pull request’s page sends it once, on the first read that shows a
  label named without a color that the envelope has no entry for
  (`github.pull-label-set` in the [Parity Registry](arch-parity-registry.md)). The pull
  envelope’s `repository_labels` are the set’s entries for the labels its record or core
  names without a color, and `labels_pending` says the job runs while the set does not
  hold one of them.

## Background Prefetch

A visible page names what the reader is likely to open next with `POST pulls-prefetch`
(`pull_prefetch.py`), which replaces the repository’s lane queue; nothing on the server
starts that work by itself, so a hidden or offline page spends nothing.
The lane is one coordinator job per served repository that runs one item at a time.
It first makes the queued file lists local where the store can give them: an open pull
request with no current comparison is listed from the head and base branch the list of
pull requests names, with every head the store lacks fetched in one Git command
(`fetch_pull_heads` in `cache/pull_refs.py`), and a served checkout attaches its store
for that if no reader has yet.
Those lists cost no GitHub request and go first; the rest alternate records and file
lists from GitHub.
The lane rereads each item from disk before it runs and stops when the
governor refuses; the module docstring works out its caps, the GitHub points they cost,
and the measurements behind the order.
A background job takes no network slot, waits behind every other job at a store turn and
is cancelled when one starts waiting, and is joined and promoted by a reader’s request
for the same pull request.
`GET pulls-prefetch` reports the lane, the caps, the governor, and recent outcomes, and
`pulls-panel.js` chooses what to name and when.

## The Comparison Keep

A pull request’s page keeps what it reads for the document, not for one page
(`createComparisonKeep` in `builtin_plugins/github/comparison-prefetch.js`), because a
page is mounted again on every visit.
Its key is the comparison’s route, which names the pull request, both commits, the
build, and the store, so a kept answer holds for as long as a record names that route,
and a record whose head or base moved names another one.
A visit to a comparison the keep holds draws its Diff summary in the paint that shows
the record, and its Changes mounts from the same answer, with no request.
A page opened on Changes reads through the keep as well, so its next visit is drawn from
it too. A request on its way is shared: a second page, a mount, or the Pulls tab joins
it, and it is abandoned only when every asker has gone.
The keep reads the comparison alone; the first screen’s rendered Markdown is the page’s
own to ask for, under the page’s own signal, since a shared request outlives any one
asker (`prefetchMarkdown` on the diff view).

- **Bound:** `KEPT_COMPARISON_CHARS` of JSON characters, with a quarter for one answer,
  least recently used first, sized in a task after the one that hands the answer on, as
  the Commits panel’s is; the measurement is beside the constant.
  A comparison past the bound, evicted or too large to keep, is read as before: once the
  browser is idle, and answered by the browser’s cache without the server.
- **Warming:** the Pulls tab warms it for the pull requests a reader opens next
  (`createComparisonWarmer`), one at a time when the browser is idle, with a cache read
  of the record and a comparison from the store, no GitHub call, within
  `WARM_COMPARISONS` an ask and `WARM_PER_HOUR`, which counts each warm before its
  record is read. Each outcome holds for the record’s freshness window, the envelope’s
  `fresh_for_s`, so a record that names no comparison, a refusal, and an answer too
  large to keep are read once rather than on every ask.
- **Not a view:** a warm’s record read carries `warm=1`, so the server does not count it
  among the records a reader viewed, which a prefetch’s `changed` refreshes.

`tests/dom/github-pull-prefetch-session.js` holds the keep and the warmer,
`tests/dom/github-pulls-files-prefetch-behavior.js` which pull requests the Pulls tab
names, and `test_a_warm_read_answers_the_record_and_is_not_a_view` in
`tests/test_github_pull_manifests.py` the flag.

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

## Drawn From Disk

Everything a mirror’s pull request page and Pulls tab draw from GitHub’s data is read
from a file beside the source or the store, so a server started on an existing cache
answers it before anything asks GitHub, and a page paints it before it starts a refresh.
`tests/test_github_drawn_from_disk.py` holds the inventory.
`ELEMENTS` names each drawn element, its route, and the Git commands the route runs in
the local store, and runs each through `metab --api` over a cache home with `gh`
failing, the remote unreachable, every Git transport command refused, and every socket
that would leave the machine refused.
`JOBS` names every other route, each of which starts or reports work, so a new route is
classified before it lands.
`test_a_diff_summary_answers_from_disk_after_the_build_changed` reads a Diff summary
after the build’s tag changes, as an upgrade or an edit of an editable install’s source
changes it, and `test_every_pull_requests_diff_summary_answers_from_disk` reads several
pull requests’ Diff summaries after each was prepared.

Four routes compute from local data rather than read a stored answer: `pull-comparison`
takes its manifest from the bank and runs Git only to check that the store answers for
both commits and their merge base and to print the first files’ hunks; `pull-image`
reads an image from the head’s tree; `pull-rendered-diff` renders both sides off the
event loop; and `pull-markdown` renders the record’s text through KPress, which keeps
the render for the process.

What a surface draws that does not answer from disk is in `GAPS`, a strict expected
failure:

- **Avatars.** Records and the catalog keep the URL; the image comes from GitHub’s
  avatar host, and only the browser’s HTTP cache keeps it
  ([Chrome](../../design-system.md#chrome) in the design system).

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
[Parity Registry](arch-parity-registry.md) names each route’s golden.

| Route | Methods | Answers or starts |
| --- | --- | --- |
| `pull` | `GET` | One pull request’s envelope |
| `pull-refresh` | `POST` | That pull request’s refresh, comparison, repair, or idle preparation |
| `pull-cores-prepare` | `POST` | A batch of lightweight cores |
| `pull-comparison` | `GET` | The record’s comparison, from the store, for Changes and the header’s Diff summary |
| `pull-image` | `GET` | An image at the comparison’s head, for its rendered Markdown |
| `pull-rendered-diff` | `GET` | One changed Markdown, YAML, or JSON file, rendered |
| `pull-size` | `GET` | The size the comparison pushes, against its merge base, and its patch’s |
| `pull-timeline` | `POST` | Conversation’s order of commits, comments, and reviews |
| `pull-markdown` | `GET` | One text of the record, or a core preview’s description, rendered inert |
| `pulls` | `GET` | A catalog window, or a search with `q` |
| `pulls-refresh` | `POST` | The catalog job |
| `pull-files` | `GET` | A pull request’s changed files |
| `pull-files-refresh` | `POST` | That list’s refresh |
| `pull-files-summary` | `GET` | What each named pull request’s cached list of changed files sums to, for its row’s change line |
| `stacks` | `GET` | The native stack snapshot |
| `stacks-refresh` | `POST` | The stack job |
| `stack-change` | `GET` | A native stack’s change line: its members’ lists accumulated |
| `labels` | `GET` | The repository’s cached label set |
| `labels-refresh` | `POST` | The label-set job |
| `pulls-prefetch` | `GET`, `POST` | The background lane’s report, or a new queue for it |
| `cache-clear` | `POST` | Removal of the plugin’s records for the repository |
| `status` | `POST` | [The GitHub status check](#the-github-status-check): `gh`, the account, its scopes, and one state |

The plugin registers two views: `pull-request`, which the shell mounts at `/pull/<n>`,
`/pull/<n>/files`, and `/pull/<n>/checks` (`pull-page.js`), and `pull-request-list`, the
Pulls tab and `/pulls` (`pulls-panel.js`). Their visual rules are in the
[design system](../../design-system.md#the-pulls-tab).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
