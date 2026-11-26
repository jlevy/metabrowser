# GitHub Pull Requests

**Status:** Built: the GitHub provider (URL reducer, `gh` runner, and rate-budget
governor), pull-request records with their commits fetched into the store, the
repository catalog and its search, lightweight cores, changed-file lists, checks in the
record, a pull request’s operational status and merge verdict beside its record, the
Conversation timeline, native stack metadata, the repository’s label set, revision
snapshots, rendered Markdown diffs, background prefetch, the page’s comparison keep, and
pull requests beside a served checkout.
Not built: opening a timeline commit in Metabrowser rather than on GitHub; the rest of
the
[merge readiness plan](../specs/active/plan-2026-11-26-pull-request-merge-readiness.md),
whose record still holds its checks and mergeability, and whose Pulls tab reads no
status and whose pages draw no verdict; and hosted releases and other providers, which
the
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
reads the active account, its token source, and its scopes from `gh auth status`, and
`gh_version` the version.
`gh_account` is every job’s account check (`gh_lists.active_account`): a conditional
`gh api user` carrying the ETag of this process’s last answer, which GitHub answers
`304` without spending rate limit while the login is the same, where `gh auth status`
spent one `core` call each time.
When it finds no account it asks `gh auth status` why, so a failure still names a
refused environment token or the sign-in command; when it cannot reach GitHub it takes
the account `gh auth status` names from what gh has saved, so a switch of account is
still seen offline. `gh_api` reads `user` and paths under `repos/` and nothing else.
Nothing there paginates or caches, because `--paginate` and `--cache` would hide page
caps, ETags, and rate-limit headers.
`gh api` refuses every request while signed out, so every record is read by an account
and names its reader as `gh:<login>`.

`gh_budget.py` keeps, per process, the newest `x-ratelimit-*` observation of each
resource every response carries, and holds every resource after a `rate_limited` refusal
until its `reset_at`. Background work is admitted only while each resource it spends has
more than `BACKGROUND_FLOOR` of its limit left and no hold applies; a reader’s own work
is never asked. Everything automatic asks: the catalog’s backfill and its periodic scan,
the prefetch, the background walk that prepares cores, the periodic reads of stacks and
of a files list, the label set, and Conversation’s timeline.
Held, each waits and is asked for again, and none records a failure.
Below the floor a visible page’s pull request and a visible list are still probed, and a
change a probe or the catalog finds is still read in full, while the reads a clock alone
asks for stop (`ServedPull.below_floor`); cores for rows on screen are read too, held
only by a rate-limit hold and the process’s ceiling.
The module’s docstring has the rule.
The observations belong to the account the last account check named, and another account
forgets them; since `remaining` is the account’s, several servers on one account stop
together.

The same module keeps a ceiling on the process’s own automatic work,
`AUTOMATIC_CORE_PER_HOUR`, counted from what the process spends itself: one for each
REST answer that is not `304` and each GraphQL query’s reported `rateLimit.cost`, over
the last hour.
The account’s `x-ratelimit-used` cannot count it, since every other client
moves it. A reader’s own action is not counted: its route starts the job inside
`readers_own`, and the job’s task inherits that.
Past the ceiling background work is not admitted (`self_ceiling`), probes slow to
`FULL_REFRESH_S`, and the full reads of what is visible to `CEILING_FULL_READ_S`, until
the hour rolls. Speculative work, which nobody is looking at, has its own share of that
ceiling, `SPECULATIVE_CORE_PER_HOUR`: the prefetch, the backfill past every reader’s
prefix, the cores walk past the rows on screen, and the label set’s periodic read run
inside `gh_budget.speculative`, which counts what they spend toward the share too, and
are refused with `self_ceiling` once it is spent.
Inside the share the backfill and the prefetch go before the cores walk, whose cost
grows with the catalog.
The walk asks with part of the share reserved (`pull_prefetch.reserved`): what the
prefetch’s caps can still spend this hour while a lane has work queued or running, a
scan’s records while a page has asked for the lane within `ASKED_WITHIN_S`, and nothing
for a lane no page asks for, so it cannot take that part between a page’s asks.
It also waits while the backfill has pages the budget admits
(`pull_cores._backfill_first`). The backfill past every reader’s prefix reserves
nothing, since Quick Search across every state and the ref chooser’s pull requests by
branch are complete only once it is, and it costs a point a page once per catalog epoch.
What is on screen is never refused for the share, so it keeps the rest of the ceiling.
`GET pulls-prefetch` reports the ceiling and the share and what the hour has used of
each under `governor.ceiling`, beside the governor’s other state.

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
| `stack-<n>.snapshots.json` | A native stack’s earlier comparison pairs, which its page keeps drawn | `pull_stack_retained.py` |
| `<n>.timeline.json` | The Conversation timeline projection | `pull_timeline.py` |
| `<n>.checks.json`, `<n>.status.refresh.json`, `<n>.checks.probe.json` | Its head’s checks as its status read found them, how that read ended, and what the probes of those checks last saw | `pull_status_store.py` |
| `catalog.sqlite3`, `list-<filter>.refresh.json` | The repository catalog, each pull request’s newest operational status in its `pull_status` table, and how the catalog’s refreshes ended | `pull_catalog.py`, `pull_list.py` |
| `statuses.scan.json` | How the last scan of every open pull request’s status ended, and what the next needs of it | `pull_status_scan.py` |
| `stacks.json` | The native stack snapshot | `pull_stacks.py` |
| `repos/<store key>/github-pull-manifests/pull-<n>.json`, `github-pull-manifest-<slot>.epoch` | Each pull request’s prepared comparison manifest, and the epochs, direct-mapped by comparison | `pull_manifest.py` |

`cache/paths.py` spells the source-side names.

## Pull-Request Records

`refresh_pull_request` in `pulls.py` is the whole network job for one pull request: the
account, then the pull request, its issue comments, reviews, and review comments, a page
at a time with `If-None-Match` from the same reader’s previous record; the account
again, discarding a record read across an account switch; then the head fetch and the
comparison endpoints; then the record; then its
[operational status](#operational-status), kept apart from the record.
A comparison whose base cannot be fetched is named in the record’s `unavailable` rather
than failing it.

The record is the pull request’s core, what changes when a person changes it.
Whether it conflicts and how its checks stand are its operational status, which it does
not hold: `PullRequest` has no `mergeable`, and `PullRecord` no check runs or combined
status, so a check that finishes gives the record no new revision and the page keeps the
conversation drawn from it.
A core (`pull_core_cache.py`) holds none either.

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

## Operational Status

Whether a pull request conflicts, how its checks stand, its review decision, GitHub’s
merge verdict (`mergeStateStatus`), auto-merge, and the merge queue change without
anyone touching the pull request: a check finishes, the base moves, or GitHub finishes a
computation. So they are a model of their own beside the record, never in it
([merge readiness plan](../specs/active/plan-2026-11-26-pull-request-merge-readiness.md)).
`pull_status.py` holds `PullStatus`, one observation of one head, and `PullChecks`, that
head’s checks, each in the bucket `gh pr checks` sorts it into.
`pull_readiness.py` turns a lifecycle and a status into the rows github.com’s merge box
would show and one verdict, and is the only place readiness is decided; its docstring
has the rules.

- **Reading.** The status is the only read of whether a pull request conflicts and how
  its checks stand. `refresh_pull_request` reads it after it publishes the record, in the
  same job, with one GraphQL query (`pull_status_read.py`), and `refresh_pull_status`
  reads it alone, with one account check and that query and no REST read of the record,
  for what changes the status and not the record: a change a probe finds in the checks
  or the mergeability, a status a window old, and a record with no status of its head
  ([Freshness Verdicts](#freshness-verdicts)). It goes through `gh_graphql`, as the core
  read does, so its `rateLimit { cost }` counts toward the process’s ceiling and its
  `viewer` must be the job’s reader.
  It pages the rollup’s checks up to `MAX_CHECK_ITEMS` and keeps the latest run of each,
  as `gh pr checks` does: a run by its name, workflow, and event, and a commit status by
  its context (`latest_of_each`). Its module docstring has the rest, and its cost,
  latency, and size are beside `_STATUS_QUERY`. Whether `mergeStateStatus` depends on
  who asks is unsettled, and the note there says why.
  GitHub answers a renamed repository’s old name under its new one, so the answer is the
  repository asked for when its `id` is the catalog’s, or, with no catalog, as GitHub
  names it (`asked_repository` in `gh_lists.py`, which the scan and the cores share).
- **Scanning every open pull request.** The Pulls tab needs a verdict for every row, so
  `pull_status_scan.py` reads the repository’s open pull requests, last updated first as
  the tab orders its rows, with one GraphQL query a page, `PullStatuses`: the same
  fields as the page’s read and the rollup’s counts by state, with no check listed.
  It builds each status as the read does (`operational_status`, `observed_by` `scan`)
  and keeps each page in one catalog transaction (`write_pull_statuses`), after the
  network and under the lock.
  `POST pulls-refresh` starts it as a job of its own, after the list’s refresh is
  started and its answer read, when a probe found a change, when a fetch moved a base
  branch the last walk’s pull requests target since that walk started, every
  `FULL_REFRESH_S` otherwise, and once `MERGEABLE_SETTLE_S` after a scan that left
  `unknown` answers, of only their pages.
  A walk keeps the mirror’s tip of each base as it started, since GitHub’s `baseRefOid`
  is each pull request’s own as of its last sync, and the ask never waits on Git: only
  when a moved base alone could start a scan does it look at the mirror, in a job of its
  own after its answer, and a mirror Git cannot read moves nothing.
  Each page it reads spaces the next scan by `SCAN_POINT_GAP_S`, which bounds what the
  scans of any repository spend an hour; the process keeps the stamp its last scan left
  as well as the file, so the spacing holds when the cache cannot keep the file.
  It reads as the catalog’s reader, with no account check of its own, and waits for the
  catalog’s first rows.
  The periodic scan waits below the GraphQL floor, and the rest go below it, as the
  catalog’s scans do; the module docstring has the rules, and the page size, the bound
  on pages, and their cost and latency on three repositories are beside `SCAN_ROWS` and
  `MAX_SCAN_PAGES`. How the last scan ended, and what the next needs of it, is
  `statuses.scan.json` (`ScanStamp`).
- **Failing alone.** A read that fails fails the status alone, as a refused part fails
  only that part of a record: the record is published and its refresh succeeds, how the
  read ended is kept in `<n>.status.refresh.json`, and what an earlier read kept stays.
  That file keeps the outcome of the attempt that began last (`StatusOutcome`), so an
  older read that fails after a newer one succeeded, as another process’s can, never
  reports a failure beside the newer status.
  A scan that fails keeps every status kept before it, and its stamp says why.
- **Budget.** The prefetch’s records, which nobody is looking at, read no status
  (`gh_budget.speculating`): its caps are priced without it (`POINTS_PER_RECORD` in
  `pull_prefetch.py`), so a prefetched record’s page reads its status when it is shown.
  Speculative work has no status read due (`ServedPull.status_due`), so the prefetch
  starts a record only when the record itself is due (`ServedPull.record_due`). Below
  `BACKGROUND_FLOOR` of either the REST or the GraphQL budget, a visible page’s
  clock-driven full reads wait (`ServedPull.below_floor`); a status read alone spends
  GraphQL, and waits below that floor alone (`ServedPull.status_below_floor`).
- **Keeping.** The status is a row of the catalog’s `pull_status` table, one for each
  pull request number, which keeps the newest observation whatever its head
  (`kept_observation` and `observation_key` in `pull_status.py`). The page’s read lists
  the checks and the scan does not, so a status’s checks summary names the read that
  listed them (`listed_at`, with the required counts that only a list gives): the newest
  keeps the latest list of an observation that summarizes the same checks, one head
  against one base and the same rollup state and counts, as long as none kept beside
  them summarized them otherwise since (`moved_at`). A scan that finds a read’s checks
  as it left them takes nothing away from it, and the status kept is the same whatever
  order the observations are written in.
  It is a table of its own, so a check that finishes moves no catalog row, fingerprint,
  core, or window generation; a catalog whose rows start over for another account keeps
  it, as the records beside it are kept.
  The checks are `<n>.checks.json` beside the record, within `MAX_PULL_CHECKS_BYTES`
  (`pull_status_store.py`), cut from the end to fit, and kept exactly when the status
  kept then counts them, so the file is always the list a status’s `listed_at` names.
  What the probes of a head’s checks last saw, each page’s ETag and a digest of what a
  status keeps of it, is `<n>.checks.probe.json` (`CheckProbes`), since the GraphQL read
  has no ETag to probe with.
  Both are in the `pulls` directory, so [clearing the cache](#clearing-the-cache)
  removes them, and a checkout without a store keeps them as it keeps its catalog.
- **Serving.** The pull envelope carries `status`, `checks`, and `readiness` beside
  `record`, and `status_unavailable` while the last read had failed.
  Each names its head, and the verdict judges a status only for the head and base of the
  record or core shown (`describes` in `pull_status.py`, which the freshness verdict,
  the served checks, and the Pulls tab’s rows ask too): another head’s, or one observed
  into the base before GitHub retargeted the pull request, is `checking`, and a closed
  or merged pull request has none.
  `checks` is only the list the status counts, of the pull request shown
  (`KeptStatus.listed_checks`): beside a scan’s status of a new head, or of checks that
  moved, it is `null`, and the page reads its own at once, once (`listing_missing` in
  `pull_freshness.py`), while its verdict is the scan’s. The entity tag covers all
  three, so a read that moves the status’s head or `observed_at` moves it.
  The page draws the verdict in its header, after the state’s badge, and in the Checks
  tab’s Merge status section, each requirement with its status and its link
  (`readinessModel` in `pull-page.js`), and only beside the state it judged: a page that
  shows the list’s fresher state instead draws none (`readinessForState` in
  `pull-readiness.js`), and the tab’s list from `checks`, each check in the ink of its
  server-side bucket, failing first, then pending, then the rest, as `gh pr checks`
  lists them, a required one marked, under `gh`’s headline for them (`checksSummary` in
  `pull-page.js`, held to `checks_sentence` by `tests/test_github_check_summary.py`).
  The verdict’s checks row counts the same list, so the two agree; without a whole list,
  as on the Pulls tab, it counts GitHub’s rollup, as `gh pr status` does.
  With a status of the head shown that counts no list, the tab shows the status’s counts
  and says the list is being read.
  A block that no required check explains, once the read knows every required one
  passes, is a Rules row (`pull_readiness.py`). `metab --show /pull/<n>/checks` prints
  the verdict and each requirement’s status on its model line.
  `GET pull-statuses` answers the kept status and verdict of up to `MAX_STATUS_NUMBERS`
  named pull requests from the cache alone, judged on the lifecycle, head, and base of
  each one’s catalog row, or `absent` with why, `other_base` among the reasons, and how
  the last scan ended (`pull_statuses_route.py`). A scan’s status from before the last
  whole walk, of a pull request that walk did not read, is `not_scanned`: one past the
  last updated the scan reads, or no longer open, whose verdict nothing keeps current.

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
  visible record last read in full `FULL_REFRESH_S` ago, a read of the status alone not
  counting; a visible page whose status alone is due (`ServedPull.status_due`), which
  reads it alone and asks the probe first when one is due, so a change it finds reads
  the record and its status in one job; and a [prefetch](#background-prefetch) that
  names it. A failed refresh is tried again after a window, and after `rate_limited` not
  before `reset_at`. A branch or tag pin never runs `gh`. A job decides what it reads
  when its turn at the store comes (`ServedPull._reads`): one a page’s ask or a prefetch
  started reads nothing if nothing is still due then, as when a hold was noted while it
  waited.
- **Probes:** a visible page asks every `probe_every_s` (`ATTENDED_PROBE_S`), and for a
  current record the server answers with a probe (`ServedPull.probe`), a conditional
  read of the pull request’s issue (`pulls.probe_path`) that GitHub answers `304`
  without spending its rate limit, and, while the kept status says its checks settle
  (`checks_settling`: a rollup `pending` or `expected`, a check in `gh`’s pending
  bucket, or no checks within `NO_CHECKS_GRACE_S` of an update), of their first pages
  every `CHECKS_PROBE_S`. The issue’s `updated_at` is the pull request’s own, and its
  ETag does not move with the repository as the pull’s does; `PROBE_RESOURCE` records
  the measurement. It carries neither the mergeability nor the head, which the read a
  change starts reads.
  The status is read with GraphQL, which has no ETag, so the checks pages are probed on
  ETags of their own, kept beside the status (`<n>.checks.probe.json`): the first probe
  of a head asks each page unconditionally, a paid `200` that seeds the baseline and
  counts as a change, one `core` a page and a status read, and every later one is
  conditional. A `200` whose digest of what a status keeps is the one kept, as a run’s
  output moving, is no change, and its ETag is kept; a page GitHub refuses marks the
  head’s pages refused, and they are not probed again.
  GitHub computes the mergeability after the read that first asks, so while the kept
  status holds an `unknown` `conflicts` or `merge_state` the probe asks the pull too,
  for `MERGEABLE_SETTLE_S`, and a known answer that differs reads the status alone; past
  that time no probe vouches for the record.
  An issue answer older than the record is one that lags, and starts nothing.
  The page’s ask names the record it shows (`"held"`, its `record_revision`), and an
  answer about that record says `record_held` in place of `record`, so the page keeps
  the one it has under the verdict the answer brings; `refresh_answer_pull` in
  `pull_route.py` records what the whole envelope cost at that cadence.
  A page that no longer holds that record reads the route instead.
  An unchanged probe vouches for the record (`verified_by: "probe"`) and keeps it
  current until the full read `FULL_REFRESH_S` asks, and so does one that found a change
  in the status alone, whose issue is as the record has it; a change starts a refresh at
  once, a change to the status alone reads only it, and a failed probe waits a window.
  Settling checks a probe cannot see (`checks_probe_paths`) leave the record to the
  window, unvouched. However many pages ask, probes of one pull request are one at a time
  and `PROBE_FLOOR_S` apart, and a rate-limit hold stops them all.
  A server runs at most `MAX_PROBES_IN_FLIGHT` at once across its pull requests, each
  one to four `gh` processes, and an ask past that answers `not_due`; one refused goes
  ahead of those probed since, for `PROBE_TURN_S`, so askers take turns; the list’s
  probe keeps its place for twice its own interval, since it asks half as often.
  A probe is a coordinator job under the pull request’s key with `:probe`, taking no
  network slot and no turn at the store, so shutdown cancels it.
- **Below `BACKGROUND_FLOOR`:** probes go on, since a `304` is free, and a change one
  finds, or the catalog reports, still starts its read.
  The `FULL_REFRESH_S` read waits until the budget is back above the floor, and so does
  an open record’s once-a-window status read below the GraphQL floor; meanwhile an
  unchanged probe keeps vouching for a record whose full read is overdue, so the page
  keeps asking every `probe_every_s`. What a probe cannot see is that much later below
  the floor. The same ask keeps the repository’s list probed (see
  [The Catalog](#the-catalog)). The
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
inside the pull request pins that commit, and a refresh can find a newer head.
A pin served under the pull request’s own `refs/pull/<n>/head` follows that head, as a
branch’s pin follows its branch
([Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)), so
the envelope names an earlier head only until the refresh job has observed the mirror.
**Browse code** is a link to the served root when the pin is the record’s head, and
otherwise a button that posts the head’s commit to `/api/source/pin`, naming the pull
request’s `refs/pull/<n>/head` as the ref to serve it under, and then opens the root, so
what moves the pin is never a link a modified click could open without moving it; a
checkout has no pin and no Browse code.
**View on branch** is Browse code for one file, on each file bar of Changes and Docs
while the diff shows the pull request’s head: a link to the file’s `/view/` address when
the pin is the head, otherwise a button that serves the head the same way first, and,
beside a checkout whose `HEAD` is the head, a link to the working-tree file.
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
**checks** when its row vouches for an open record whose kept status is missing, of
another head, or observed longer ago than the window, since `updated_at` does not move
for checks or mergeability, and **unverified** otherwise; the module docstring states
each rule. A `checks` record is current: it holds nothing `updated_at` does not track,
and only its status is read again, alone.
Whatever the verdict, `status_missing` says no kept status of the record’s head counts a
list of its checks, as a scan’s of a new head or of moved checks counts none, which a
visible page then reads, at once for a scan’s status newer than its last read
(`unlisted_at`); and `checks_pending` says the status’s checks or mergeability are still
settling. A [list probe](#the-catalog) that found the catalog unchanged counts as a scan
run when it asked, so the catalog vouches between scans.
`verified_at` and `verified_by` say when and how the record was last known to describe
GitHub: by the catalog’s scan or list probe, by its own fetch, or by a
[probe](#serving-pull-requests) of the served pull request.
They move with every scan and probe, so the entity tag leaves them out and
`x-metabrowser-verified` carries them.
`cli-github-pulls-prefetch.txt` pins each verdict.

## The Catalog

`pull_catalog.py` keeps one SQLite catalog per repository of lightweight rows, with
indexes on `(updated_at, number)` and `(state, updated_at, number)`. Merged rows are
closed. Its checkpoint holds the repository identity, the reader, GitHub’s counts, the
cached counts, the scan cursors, freshness, and content generations.
Listing takes a `ListedRepository` and never a store, so a checkout without one has a
catalog.

**Writing.** `pull_list_refresh.py` reads GraphQL pages of at most `PAGE_SIZE` rows
(`pull_catalog.py`), with no description, comment, review, check, or patch: the reader’s
filter prefix first in update order, as far as the reader has scrolled, then the
backfill of every pull request in creation order using a separate cursor.
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
A pull request’s [status](#operational-status) is written the same way, into a table of
its own, and moves no row, checkpoint, or generation.

**Probing.** `pull_list_probe.py` asks GitHub whether the catalog is behind with one
conditional request for the issue or pull request updated last (`probe_path`), which
GitHub answers `304` without spending its rate limit.
It asks the issues list, which includes pull requests, because a pull request’s own row
embeds its repositories and its ETag moves on every push; the measurements are beside
`LIST_PROBE_S`. When an issue is the newest row, the one-row pulls page (`pulls_path`)
says which pull request is.
GitHub’s lists run behind a change, so that page is asked by every probe until one asks
it `PULLS_LAG_S` after the issue’s update, and until then an unchanged probe vouches
only for what GitHub had that long before it asked.
A `200` is a hint: the newest pull request is compared with the catalog’s row of that
number, and the catalog is behind only when it lacks that row as GitHub has it.
An unchanged probe moves the probe’s `checked_at`, and for a freshness window the
catalog vouches as a scan run then would, so the list stays `current` and its records
[verified](#freshness-verdicts) between scans.
A change starts the job with its delta scan first, once for each row; a row still
missing after its scan, as when GraphQL lags REST, leaves the scan to the window.
A visible Pulls tab asks every `probe_every_s` of the list’s envelope (`LIST_PROBE_S`),
and a visible pull request page’s own ask does the same for its repository
(`attend_list` in `pull_list_route.py`), so the list is probed while either is on
screen. `refresh_wanted` decides each automatic ask: the catalog job when the list is
absent, failed and due, or wanted for a reader’s prefix or the backfill; the delta scan
once every `FULL_REFRESH_S` while probes vouch and once a freshness window otherwise;
and else the probe, one at a time for a repository and `LIST_PROBE_FLOOR_S` apart
however many tabs ask.
A change a probe found is asked for before the periodic scan, so the job that scans for
it is the one the probe is told of.
Two asks that both found the probe due in their worker threads start one probe: the
later finds it no longer due on the loop and starts nothing.
A list probe counts toward the server’s `MAX_PROBES_IN_FLIGHT` with its pull requests’
probes and is a coordinator job as theirs are.
Probes that each pay for a `200` and find no pull request changed, as in a repository
whose issues never rest, grow further apart, up to `MAX_PAID_PROBE_S`. The module
docstring gives each outcome, `tests/test_github_pull_list_probe.py` pins them, and
`cli-github-pulls-probe.txt` shows an ask answered by a probe.

**Admission.** Reads open the database read-only and run neither Git nor `gh`. Readers
and writers admit only declared table and index layouts and refuse a write-ahead-log
database before SQLite opens it.
A catalog a newer release wrote declares it, in `user_version`, the checkpoint’s schema,
or a row’s projection, and is left as it is with the refresh ending `newer_cache`,
because several builds can share one cache.
One whose versions cannot all be read safely ends `unknown_cache`. One an earlier
release wrote, of a version `_UPGRADES` names and with exactly its schema, is brought to
this schema in place, its activity indexes and status table added, by the first ranked
list read or refresh or by the first writer, in that write’s transaction under the
source lock. The local upgrade preserves cached rows and needs no GitHub access.
The checkpoint retains the creation-order backfill cursor and clears incomplete prefix
coverage so each filter can resume in update order.
Anything else a writer cannot use is replaced with an empty catalog under the lock.
The module docstring gives each case, and `tests/test_github_pull_list.py` pins the
shape each version names.

**Reading.** `GET pulls` answers an indexed window of up to `MAX_WINDOW` rows below the
`after` row. Each filter orders by descending update time and then descending PR number.
GitHub’s counts are dated by `count_at`. For an exact PR lookup, `state=all` and `at`
return its row and its zero-based position in All, capped at `limit`. A per-filter
`generation` changes when existing content or the leading prefix changes, not when older
pages are appended, so a client replaces a held window only after collecting one under a
single source, reader, and generation.
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
A GitHub list with no catalog row to check it against ages by `FULL_REFRESH_S`; one the
row vouches for is not read again on a clock, since it is a function of the head and
base it names and is read at once when either moves.
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
pin is the head, and otherwise points at that file at the head on github.com (`headFile`
in `builtin_plugins/diff/index.js`). `pull_snapshot.py`’s docstring lists every outcome
code.
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
The render makes links absolute against the pull request’s page and marks authored
path-relative references before that conversion.
`static/repository-links.js` reads marked references against the pull request’s head and
can open a changed head-side path in Changes.
An authored absolute URL follows its own GitHub route.
See [In-App Link Resolution](../specs/active/plan-2026-11-26-in-app-link-resolution.md).
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

## Changes Follows the Head

Changes shows the record’s comparison, so a record read at a newer head, or against a
base that moved, replaces the diff on screen without the reader asking.
The owner set this on 2026-11-22 (bead `mb-6a6w`), replacing the diff that stayed until
**Show the newer changes**: with a visible page probed every few seconds, that offer
appeared seconds after every push of a review.
The served code follows the same head
([Following a Branch](arch-mirror-acquisition-and-refresh.md#following-a-branch)). Docs
draws the same comparison, its documents alone, through the same `paintFiles`: it
follows and notes a moved head and keeps the reader’s place as Changes does, and its
history entry remembers what it showed (bead `mb-mzcj`).

- **The decision:** `filesAction` in `pull-page.js` answers `follow` for a mounted diff
  whose comparison is no longer the record’s. A refresh the reader asked for that finds
  another head is followed too, not repaired first.
- **The note:** the diff that was replaced is kept (`followedFrom`), and `followedNote`
  says what the line above the new diff names: both heads, or, for the same head from
  another merge base, that the comparison changed.
  **Show the earlier changes** mounts the replaced diff from its own routes, which name
  two immutable commits.
  That diff is the reader’s choice, so `filesAction` answers `offer` for it and it stays
  until **Show the newer changes**, also through a reload, since the history entry
  remembers the choice (`chosenEarlier`). A move between Changes and Docs draws the diff
  the reader chose, or else the record’s comparison as read now (bead `mb-825n`);
  leaving both for another tab ends the choice, since that tab’s paint disposes the diff
  and the next one mounts the record’s.
- **Across a reload:** on a repository URL the page reloads when the served pin follows
  the head, because a page names its pin on every data request
  ([Source Sessions and Pins](arch-source-sessions-and-pins.md)). So the history entry,
  on Changes or Docs, remembers the comparison last shown and the one its note named
  (`rememberedChanges`), and whether the reader chose the earlier one, beside the
  reader’s place. A page loaded again on an entry that showed another comparison says so
  in the same line, and one whose reader chose the earlier diff shows it again with the
  offer of the newer. An entry reached by Back after the head moved says it too.
  The page writes the memory when it mounts a diff and when the page host lands it on an
  address of its own (`setTab`, `land`, `showFile`), since the shell writes each entry
  it makes with no state.
  A key’s walk of the Pulls tab’s changed files replaces the entry once it stops, and a
  click on a file pushes one, neither mounting a diff (bead `mb-eg5f`). Writing the
  memory in the page, rather than having the shell keep a replaced entry’s state, covers
  the push too, and keeps the page the only writer of what it put there.
- **The reader’s place:** a place in Changes names its file (`PanePlace`), which the
  mounted diff maps to a block and back, so the place held through a replacement, or
  landed on after a reload, is in the same file, at the same offset, where the new diff
  has that file. A file the new diff lacks puts the reader at the top of the block at the
  place’s index, since the offset was a line of a file that is gone.
  The place is held and written to the entry before the old diff is taken away, so the
  emptied pane’s clamp to its top, which arrives as a scroll, writes nothing while the
  new comparison is read, and a reload in that time lands on the reader’s file.
  From the new diff’s arrival the hold is a landing’s: it lasts until the page is still
  or the reader moves.

`tests/dom/github-pull-page-session.js` pins the decision, the note, the entry’s memory,
and the place; `tests/dom/github-pull-repair-lifecycle-behavior.js` and
`tests/dom/github-pull-page-mount-behavior.js` drive them through the mounted page.
`tests/dom/github-pull-changes-follow-behavior.js` drives the join: a mounted page with
a history entry, whose diff view answers `sectionForPath` and `pathForSection` from its
own sections, follows a head, keeps the place through the emptied pane, and is mounted
again on the entry, on Changes and on Docs, moves between the two, and is landed on a
file through the production page host by a walk and by a click;
`tests/dom/diff-file-jump-session.js` pins the two accessors of the production diff
view.

## Conversation Timeline

`POST pull-timeline` (`pull_timeline.py`) gives Conversation the order of commits,
comments, and reviews from GitHub’s timeline connection, for a record revision the page
names. It reads at most `MAX_PAGES` pages of `PAGE_SIZE` events and keeps the projection
in `<n>.timeline.json`, bound to the inputs it orders (`_discussion_revision`): the
source, number, reader, base branch, head, and the discussion’s identifiers.
An advance of the base branch keeps it usable; a retarget or a new head needs a new one.
It answers `complete`, `partial` with a retryable verified prefix, or `unavailable`,
retryable with `retry_after_s` when the budget held the read, which the page asks again
after for as long as the budget holds it; it asks for no patch or Git object, and runs
only after the selected Conversation paints, in a provider slot of its own once any
metadata refresh settles.

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
Nothing reports a stack’s change, so a snapshot that was read is read again
`FULL_REFRESH_S` later while a view asks for it, one conditional page when nothing
changed; a failed attempt waits `STACK_FRESHNESS_S`.

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
governor refuses, except for the lists the store gives, which cost GitHub nothing and
are listed whatever the governor says; the module docstring works out its caps, the
GitHub points they cost, and the measurements behind the order.
A background job takes no network slot, waits behind every other job at a store turn and
is cancelled when one starts waiting, and is joined and promoted by a reader’s request
for the same pull request.
A reader who joins a pull job that was already told to stop, a background one or a
checkout’s optional comparison, has it started again as theirs once the stopped one has
unwound, on a mirror and on a folder’s checkout alike
(`RefreshCoordinator.start_again_when_stopped`). `GET pulls-prefetch` reports the lane,
the caps, the governor, and recent outcomes, and `pulls-panel.js` chooses what to name
and when.

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
  `"retry": true, "comparison": true`, which asks core for the checkout’s store
  (`acquire_checkout_store` in `checkout_store.py`), an overlay with the checkout as
  lender
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout))
  or reuses a healthy store, and leaves the served folder and its Commits tab unchanged.
  It first waits out another process’s cold open of the source.
- **Idle preparation:** once a store is attached, a visible Conversation can ask for a
  current record’s comparison as optional work (`"prepare_comparison"` with the record
  revision). It fetches only that pull request’s head and base, never deepens, holds no
  network slot, and records no outcome; a reader’s Changes request promotes it, and
  another pull request’s refresh cancels it while it is still optional.
  Once a reader’s request has promoted it, it runs on as theirs.
- **Repair:** Changes offers Refresh for a displayed comparison even while the record is
  fresh. The request carries `"recovery": {"base": …, "head": …}`, which the server
  accepts only for a pair this session issued for that pull request (the last
  `MAX_ISSUED_COMPARISONS`), then runs the
  [object recovery](arch-mirror-acquisition-and-refresh.md#object-recovery).
  A successful repair remounts the same comparison once, and a failed one leaves it in
  place. A refresh that finds another head is followed instead
  ([Changes Follows the Head](#changes-follows-the-head)).

`GET` routes never acquire or fetch.
What a reader sees for each failure name, and what to do, is in
[Reviewing Pull Requests](../../reviewing-pull-requests.md).

## Drawn From Disk

Everything a mirror’s pull request page, stack page, and Pulls tab draw from GitHub’s
data is read from a file beside the source or the store, so a server started on an
existing cache answers it before anything asks GitHub, and a page paints it before it
starts a refresh. `tests/test_github_drawn_from_disk.py` holds the inventory.
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

Several routes compute from local data rather than read a stored answer:
`pull-comparison` takes its manifest from the bank and runs Git only to check that the
store answers for both commits and their merge base and to print the first files’ hunks;
`pull-image` reads an image from the head’s tree; `pull-rendered-diff` renders both
sides off the event loop; and `pull-markdown` renders the record’s text through KPress,
which keeps the render for the process.
`guided-review` reads the description and comparison manifest, then hydrates only the
files whose excerpts the selected step needs.
`stack` asks the store whether the top’s head holds the bottom’s merge base, then reads
the stack’s kept manifest, and `stack-comparison` serves that manifest as
`pull-comparison` serves a pull request’s.

What a surface draws that does not answer from disk is in `GAPS`, a strict expected
failure:

- **Avatars.** Records and the catalog keep the URL; the image comes from GitHub’s
  avatar host, and only the browser’s HTTP cache keeps it
  ([Chrome](../../design-system.md#chrome) in the design system).

## Clearing the Cache

`POST cache-clear` takes an empty object and removes every entry of the source’s `pulls`
directory (`clear_pulls` in `pull_record.py`), the catalog with its statuses and each
pull request’s checks among them, under the source-alias lock every writer of those
files takes; each is fetched again when next wanted.
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
| `guided-review` | `GET` | One ordered step and its excerpts from the cached PR description and pinned comparison |
| `pulls` | `GET` | A catalog window, or a search with `q` |
| `pulls-refresh` | `POST` | The catalog job, and the scan of every open pull request’s status when it is due |
| `pull-files` | `GET` | A pull request’s changed files |
| `pull-files-refresh` | `POST` | That list’s refresh |
| `pull-files-summary` | `GET` | What each named pull request’s cached list of changed files sums to, for its row’s change line |
| `pull-statuses` | `GET` | Each named pull request’s operational status and verdict, for its row’s readiness ([Operational Status](#operational-status)) |
| `stacks` | `GET` | The native stack snapshot |
| `stacks-refresh` | `POST` | The stack job |
| `stack-change` | `GET` | A native stack’s change line: its members’ lists accumulated |
| `stack` | `GET` | A native stack’s page: its members, what its header says of them, its combined comparison’s address, the members its top lacks, and each file’s layers; with `since`, how each member’s head moved from a comparison it answered before ([The Stack Page](#the-stack-page)) |
| `stack-comparison` | `GET` | That combined comparison as a diff document |
| `labels` | `GET` | The repository’s cached label set |
| `labels-refresh` | `POST` | The label-set job |
| `pulls-prefetch` | `GET`, `POST` | The background lane’s report, or a new queue for it |
| `cache-clear` | `POST` | Removal of the plugin’s records for the repository |
| `status` | `POST` | [The GitHub status check](#the-github-status-check): `gh`, the account, its scopes, and one state |

The plugin registers three views: `pull-request`, which the shell mounts at `/pull/<n>`,
`/pull/<n>/conversation`, `/pull/<n>/files`, `/pull/<n>/guided`, and `/pull/<n>/checks`
(`pull-page.js`); `pull-stack`, a native stack’s page at `/stack/<n>`,
`/stack/<n>/guided`, `/stack/<n>/docs`, and `/stack/<n>/changes[/<path>]`
(`stack-page.js`); and `pull-request-list`, the Pulls tab and `/pulls`
(`pulls-panel.js`). Their visual rules are in the
[design system](../../design-system.md#the-pulls-tab).

### The Stack Page

A native stack’s page shows the whole stack as one comparison
([Whole-Stack Review](../specs/active/plan-2026-11-24-stack-review.md#phase-1-the-stack-page-mb-vad1)).
`pull_stack.py` holds the rules, and its module docstring states them with the
measurements that set them:

- **The comparison** runs from the bottom member’s merge base to the top member’s head,
  and keeps only the files some member’s own comparison names, on either side of a
  rename. A member the top’s head does not contain, by its head or its merge commit, adds
  no file and is named in `lacking`; a bottom merge base outside the top’s history
  answers `absent` with `not_linear`.

- **Its identity** is the store, both commits, and a digest of every member’s number,
  merge base, and head in stack order (`stack_key`). The digest is in the comparison’s
  address, its in-memory key (`scope` of the diff plugin’s `comparison_at`), its entity
  tag, and its kept manifest beside the store (`load_stack_manifest` in
  `pull_manifest.py`), so a member that moves names a new comparison and nothing is
  invalidated by hand.

- **The header’s sums** are what the page’s header says of the stack where a pull
  request’s says it of one pull request: `states`, `opened_at`, `updated_at`, `authors`,
  `mergers`, `fetched_at`, `labels`, `commits`, and `size`, each from what the cache
  holds of each member, its record’s or else its cached list row’s, as its title is.
  The commits count the members the top contains.
  The size is the combined comparison’s own, measured where the comparison is built
  (`combined`), once a pair and kept beside the store, and only where that comparison is
  the plain diff of its two commits and at most `MAX_SIZED_STACK_FILES` files, so the
  size and the file count describe one diff.
  The first read after a member moves builds the comparison, so it waits on the
  measurement too, which is bounded by the file cap and `MEASURE_TIMEOUT_S`; every later
  read takes it from `kept_change_size` and runs no Git for it.
  The size is asked to an answer once a kept comparison: a size, a reason Git has none,
  such as a measurement that ran out of time, or that the comparison is not one that is
  measured. The stack’s kept manifest is then marked (`_settle_size`, `size_settled` in
  `pull_manifest.py`), so a read that finds it kept and marked runs no Git for the size,
  in the process that asked or a later one, as every `metab --api` read is.
  A manifest found kept and not marked, as an earlier build left it, is asked by the
  read that loads it, which lists the plain diff once more.
  A measurement Git failed, or whose read was cancelled, is no answer, and the next read
  asks again.

  `labels` is null while a member has neither a record nor a row, and its names are the
  row’s wherever there is one (`member_identity`), as the stacks route’s are.

- **Admission.** `pull-rendered-diff` and `pull-image` take `stack=<n>` in place of
  `number` and admit the stack’s current pair, and `stack-comparison` lists it
  (`_stack_admission` in `pull_snapshot.py`). Each keeps answering a pair the `stack`
  route answered after the stack moves, since a page keeps the comparison it drew:
  `pull_stack_retained.py` keeps a stack’s last `MAX_RETAINED_STACK_PAIRS` pairs in
  `sources/<slug>/pulls/stack-<n>.snapshots.json`, for the store that computed them and
  the reader whose records named them, as `pull_snapshot_cache.py` keeps a pull
  request’s. A pair no longer kept answers `stack_moved` or `snapshot_expired`, and a
  file that cannot be read now answers `snapshot_unavailable` (409).

- **The page** (`stack-page.js`) is a pull request’s page for the whole stack
  ([The Stack Page](../../design-system.md#the-stack-page)): a pull request’s page
  header said of the whole stack, with its members, top first, the stack menu’s rows
  (`stack-member-row.js`), under a toggle above its last line, the Diff summary, both
  closed; then Docs with `DOCS_DRAWING` and Changes with `CHANGES_DRAWING`
  (`diff-drawing.js`, which `pull-page.js` shares), with no layer marks.
  Every header row but the status line is decided at first paint from the stack snapshot
  (`stackHeader`), the labels row by the members’ labels the stacks route projects
  (`labels`, `knownLabels`) and held where it does not know them all, and the members
  row held even for a stack the snapshot lacks; the page is held cold until the stack’s
  answer fills the rows the snapshot cannot, and Docs and Changes are laid out out of
  sight until their first screen is ready, as a pull request’s are.
  Its View on GitHub is the counterpart route’s, GitHub’s `stack/<n>`. It polls `stack`,
  asks `pull-refresh` for each pending member at its head, a member with no record as
  the reader’s own open of it (`retry`), since an automatic ask refreshes only a record
  the server holds, and sends the top member’s automatic ask the answer’s `probe` names.
  An ask the server refuses (429, past `MAX_PULL_JOBS`), that fails, or whose fetch ends
  with the member still pending is sent again after `ASK_BACKOFF_MS`; each member’s
  `fetching` says whether its fetch was running before its record was read (asked on the
  loop first, as `PullView` asks), so the page tells one under way from one that ended.
  A member with no record whose fetch ended without one is named as failed, with a
  Retry, once a second read finds it so.
  A hidden page does not poll.
  A comparison the page drew stays while the stack is pending or refused, and when a new
  one looks the same, the same two commits, files, and totals.
  One that looks different is drawn in its place until the reader first moves on the
  page; after the reader’s move, it is held while a member it waits on is fetched and
  then offered, the notice saying what changed in each member (`answerAction` and
  `changeText`). The poll asks `stack` with `since`, the key of the comparison drawn.
  The write of a new pair keeps that one just before it (`retain_stack_pair`), and a
  poll that names another pair than the last write kept writes again, so with two pages
  open on one stack each keeps its own; the pair a page draws stays admitted unless more
  than `MAX_RETAINED_STACK_PAIRS` moves come between two of its polls, as they can while
  it is out of sight. An answer without `moved` says the pair drawn is gone: the page
  draws the new comparison in its place if it looks the same and otherwise offers it at
  once, and a guide step the route refuses as `stack_moved` makes the page read the
  stack then rather than at its next poll.
  The answer’s `moved` gives, for each member in both whose head moved, the commits its
  new head adds that the comparison drawn did not show, in neither the earlier head’s
  history nor its top’s, nor its merge base, or `null` when the earlier head is not in
  its history, or 0 when the top drawn holds the new head and not the earlier one, a
  record that caught up (`stack_moves`, read against the pair `pull_stack_retained.py`
  keeps for that key and counted once each, `MAX_KEPT_COUNTS`). A file the reader opens
  is scrolled to when its diff is drawn, never on a later answer (`bodyPlan`).

- **The guide.** When a member’s description carries the stack’s guide, the answer’s
  `guide` names that member and its record revision, Guided Review leads the tabs, and
  `/stack/<n>` opens on it; without one the front page is Changes
  ([The Stack’s Guide](#the-stacks-guide)).

### Guided Review

A guided review is the pull-request carrier of the
[collection format](arch-collection-format.md): the format is general, and this section
describes what the carrier adds.
`guided_review.py` extracts a top-level fence from the raw, bounded PR description and
validates its artifact against the installed `Collection/v1` SoftSchema
(`metabrowser.collection:Collection/v1`), whose ordered `items` are the guide’s steps
and groups of them, one level deep.
The steps are numbered 1 to the step count in reading order, through the groups
(`Collection.flat_items`), so `step=<k>`, the page’s step addresses, and a stale guide’s
`changed_steps` count them alike.
An undeclared key or a list past its bound is refused before the schema runs
(`_outside_shape`), since softschema’s refusal costs time quadratic in the number of
undeclared keys, and a record for each element of a long list.
The request names a PR and an optional one-based step.
The handler checks both comparison endpoints and a newer head GitHub’s list knows, and
hydrates just the paths that the chosen step needs through the same manifest and diff
adapter as Changes, at the pull request’s current comparison, whose manifest is the one
the record keeps (`pull_manifest.py`). A stale guide’s steps are read there too, so a
push, a rebase, or a force push leaves the guide readable whether or not the store still
has the commits it was written for.
Unresolved references are reported in place.
Pins whose `merge_base` the store has and is not an ancestor of the guide’s head do not
name a comparison and are answered `invalid` (`_pins_compare`); a head the store lacks
is what a force push leaves, so it is stale, not invalid.
A guide whose pins are not the pull request’s current comparison is answered `stale`
with its step and a `stale` object (`_staleness` in `guided_review.py`): both
comparisons, the first-parent commits after the guide’s head or that its head left the
branch’s history, and the cited paths whose content changed between the two comparisons,
compared path by path with no rename detection, and the steps that cite one, each with
its bound beside its constant, or `null` when the store lacks the guide’s head.
When GitHub reports a head this copy lacks, the guide is stale too, and what the newer
commits changed is unknown, so neither list is answered.
A `comparison_unavailable` answer for a stale guide carries the `stale` object too.
Those details are for agents and the goldens; the page says less (`staleNotice` in
`guided-review.js`): one warning and one remedy when a cited file changed or what
changed is unknown, a quiet line when none did, and nothing when this copy matches the
guide and only GitHub’s head is newer, since the page’s header already says new commits
were pushed.
It marks each changed step, in the step list and on the step, and says above
a changed file’s excerpt, or in its place, that the file changed, and when what changed
is unknown that it may have; it names no commit, head, merge base, path, or count.
The limits in `guided_review.py` (`MAX_ITEMS`, `MAX_REFERENCES`, `MAX_EXCERPT_BYTES`,
and `MAX_STEP_PATCH_BYTES`) cap the guide’s steps and groups together, the per-step
hydration, the excerpt text, and a step’s whole files, each with the measurement that
set it beside the constant.
The parse is kept for each pull request by record revision, so a step click reads the
guide the first request parsed and an edited description is parsed once, by the first of
the requests that ask for it at once.
An excerpt shows a replacement whole: `_hunk_rows` includes a line that exists only on
the other side when it lies inside the range or touches either end of it.
A note is Markdown, rendered as the description is: each answer with a step carries its
note’s render as `note_html`, and the step that opens a group with a note carries that
note’s as `group_note_html`, each produced by the description’s own path (`render_text`
in `pull_text_render.py`: KPress in its sanitized mode, then `harden`, in the Markdown
child under its deadline) and kept with the guide’s parse for the record revision within
`_MAX_KEPT_NOTE_CHARS` (`_rendered_note` in `guided_review.py`). A refused render
answers null, with the refusal’s code beside it as the pull-markdown route answers a
text’s (`note_refusal`, `group_note_refusal`), and is not kept: the child keeps the
refusals that are the note’s doing, and renders on the next read after a busy or
unavailable renderer.
The page shows a refused note as typed, with the line a description’s refusal says
(`textRefusalNote` in `pull-page.js`), and keeps no answer whose renderer was busy or
could not start, so the step is read again.
The page inserts a render through the description’s allowlist (`inertProse` in
`pull-page.js`), and draws no Mermaid diagram from a note.
Titles and diff lines are inserted as text, in the design system’s existing parts: each
step is a page card headed by the Guided Review badge and its place, as Conversation
draws a comment, its title and note prose in a KPress article, as a description is, and
each excerpt is drawn by the diff plugin’s own renderer (`mountFilePatch`, which the
page loads with `plugins.load("diff")`; `renderReference` in `guided-review.js`), so its
hunk bars, folds, type, row height, gutter, and change fills are Changes’.
Each card the guide draws for a file folds by the diff view’s own bar and chevron, which
the guide’s drawer hands over (`disclose` on `guidePatchDrawer`, the diff view’s
`fileDisclosure`), so the guide builds no bar of its own
([Diff File Bar](../../design-system.md#diff-file-bar)). A range is one hunk in the diff
model’s shape (`_rows_hunk` in `guided_review.py`), and a path alone is its file’s whole
patch, within the step’s budget for whole files; a file past it, or past what the diff
source reads in one run, is answered `patch_too_large`. A path alone of a file the
rendered route renders, by that route’s own rule on both sides of the change
(`rendered_format` in `pull_rendered_diff.py`: Markdown, YAML, JSON), is a document
instead: the guided route answers its format as `rendered`, reads no patch for it, gives
it no hunks, and charges it nothing against the step’s budget for whole files
(`_step_references` in `guided_review.py`), so a large document is bounded only by the
rendered route’s own bounds.
The page draws it (`referenceDrawing` in `guided-review.js`) with the diff plugin’s own
view of that file (`mountRenderedFile` in `diff/index.js`): a Markdown file with the
options the Docs tab gives its documents (`DOCS_DRAWING` in `diff-drawing.js`), and a
YAML or JSON file, which Docs does not list, with the options Changes draws with
(`CHANGES_DRAWING`), so its file bar, its rendered layer and that layer’s chooser, and
its Diff and Current are that tab’s, and whatever the tab learns to draw a file with,
the step’s document draws with too.
The view reads the comparison route’s one-file answer by path, whose manifest entry
carries the id the rendered route asks for.
The page draws a document only while its own comparison is the one the step was read at;
at another, the reference says its file’s diff is unavailable, and with no rendered
route the view draws the file without the rendered layer.
A document the view could not draw keeps the guide’s bar for it, with its name and its
Open full diff, above the view’s one-sentence notice.
Each document is in the step’s list of drawn views, so a step change, or the page
ending, disposes it and aborts its read.

The page shows a step whole (`compose` and `present` in `guided-review.js`): it draws
the step out of sight, beside the one shown, and replaces that one in a single change
once the step’s answer, the text’s stylesheets, its drawers, each document’s first
screen (`settled` of `mountRenderedFile`, held for its rendered layer for
`GUIDE_DOCUMENT_HOLD_MS`), and on the overview the description’s Markdown are in hand,
the last waited for at most `GUIDE_INTRODUCTION_HOLD_MS`. Its reads go through the
document’s keep, `guide-reads.js`: one answer per step, record revision, and whether
GitHub reported a head past that record when it was read (`show`’s *moved*, since the
server then answers the steps as out of date with the same revision), a read in flight
shared by whoever asks for it the same way, never kept when it holds what a later read
answers otherwise (`retryable`: a note a busy renderer refused, or a reference
`not_cached`, `comparison_unavailable`, or `diff_unavailable`), and let go oldest first
past `GUIDE_KEPT_CHARS`. A pull request’s page reads the first step ahead, when it is
idle on another tab or beside the module’s import on Guided Review’s own, a stack’s page
at the comparison it draws, and the guide reads the steps next to the one shown when the
page is idle (`createGuideNavigation`’s `prefetch` and `peek`), so a step one move away,
or one read before, shows in the same task as the press.
A step’s documents are not read ahead: they are drawn as it is composed, and the arrows’
delayed mark shows while they are (mb-ukmm).
A step can also cite past its pull request, with the format’s other
[reference kinds](arch-collection-format.md#the-record), each answered with its `kind`
and every field, null where its kind has none (`_references` in `guided_review.py`), and
each read from this copy alone, never stale, and never counted in `changed_steps`
(`_own_paths`), except a `{pull, path}` that names the guide’s own pull request, which
is a `{path}` (`_carried`). A `{pull}` is that pull request’s title, state, and author,
from its cached record or else its row in the list of pull requests, and its place in a
stack from the stack snapshot, preferring the stack that holds the guide’s own pull
request (`_pull_targets`), or `not_cached` when this copy knows neither; its address is
the pull request’s page.
A `{pull, path}` is that file at that pull request’s current comparison, read from its
record’s kept manifest with one run of the diff source for each pull request the step
cites, within the step’s one budget (`_pull_files`): the answer carries that
comparison’s pins and the routes that answer it, which the page draws a document from,
and is `comparison_unavailable` when this copy cannot read it, or `not_cached` when it
has no record or no manifest kept for the record’s comparison, which a refresh keeps
(`prepare_pull_manifest`) and this route never lists; its address is the file in that
pull request’s Changes, which loads it.
A `{commit}` is its subject and committer date, read for every commit of the step by one
bounded `git log` in the store (`_commit_targets`), or `commit_unavailable`; its address
is `/commit/<sha>`, which the page opens as a plain link, unless the server browses a
checkout, whose Git that page reads instead of the store, and the checkout lacks the
commit: one fetched only with a pull request then has no address, and its row says it is
not in this checkout.
`MAX_REFERENCES` records what each kind costs a step.
The page draws a `{pull}` as the stack menu draws a member and a `{commit}` as the
Commits tab draws a commit (`pullRow` and `commitRow` in `guided-review.js`), and a
`{pull, path}` as a `{path}`, under a bar that names its pull request, whose Open full
diff opens the file in that pull request’s Changes.
A ready step carries KPress’s stylesheet manifest, as the description’s Markdown route
does, and the page loads it and the diff plugin’s styles before drawing the step, so the
tab reads the same when it is the first thing opened.
Guided Review is the first tab when the description has a guide: it is the author’s
reading order. `/pull/<n>` is then the guide, and Conversation is
`/pull/<n>/conversation` (`shownTabFor` in `pull-page.js`); without a guide `/pull/<n>`
is Conversation, and its `/conversation` address shows Conversation either way.
The controller and the page resolve the front page from one text, the record’s
description or before it the core preview’s (`textSource`), so a preview of a guided
pull request opens on its guide.
A tab’s link and key go to the front page when it shows that tab (`routeForTab`), so
they never open a second history entry of the page on screen.
The description introduces the guide, and a collection has no prose of its own:
`render_part` in `pull_markdown.py` renders the description, a core preview’s too,
without a guided-review block that reads as a guide (`guide_introduction` in
`guided_review.py`, from the route’s kept parse, off the event loop), the Guided Review
tab opens with that render, and Conversation puts a card that opens the guide in the
block’s place. A block that cannot be read stays in the description, so its author sees
it. The description is the guide’s step 0, its overview (`createGuideNavigation` in
`guided-review.js`): the page draws it from the description it already has, under a list
of the steps that a step answer’s `titles` fill, and it keeps the answer for step 1 that
it read for those titles, so the first move reads nothing.
Each answer with a step carries the guide’s `outline` (`_outline` in
`guided_review.py`), a tree in reading order of group nodes, each a title, a note or
null, and its steps, and step nodes, each its number and title; the step’s own `group`
is the index of its group’s node, or null.
The step list draws each group as the shell’s group heading, with no number and nothing
to press, above its steps, which keep their flat numbers, built once for each outline as
the rows are; a step’s card names its group before its place (`groupedPlace`), and a
group’s note shows above its first step.
A guide without groups is an outline of steps alone, which draws as it did before
groups. A stack’s guide answers the same tree ([The Stack’s Guide](#the-stacks-guide)).
Each answer with a step is kept for its record revision, and a new revision or a moved
head drops them. A step whose read is refused or fails keeps the guide’s steps, so the
reader can move on, and is read again when chosen again.
`guided-review.js` loads on demand when the tab opens, aborts reads on disposal, and
matches results to the page’s record revision.

The tab is shown from a hint, not from the parse: `GUIDED_FENCE` in `pull-page.js`
matches a line that opens a `guided-review` fence in the description, and the server’s
reading, which counts only a top-level fence, decides what the tab shows.
A description that documents the format inside another fence therefore shows a tab that
says the pull request has no guide, and since the hint also picks the front page, that
page is `/pull/<n>`, with Conversation one click away.
Letting the server answer for the tab, with a `has_guide` on the `pull` envelope, would
change an envelope the browser and every `--api` golden of the route share, so it is not
done here; mb-y0en tracks it, with a way to check a guide before it is published.

### The Stack’s Guide

A native stack’s guide is the collection carrier of a whole stack
([Whole-Stack Review](../specs/active/plan-2026-11-24-stack-review.md#phase-3-the-stack-guide-mb-ri96)):
a top-level `stack-review` block in a member’s description, read by the parser that
reads a `guided-review` block (`_guide_fence` takes the fence’s name).
A description may hold one block of each name, and two of either is refused; a block
that cannot be read does not keep the other from being read (`_read_description`). An
edit of a description moves no head, so the guide costs no CI run and leaves the
member’s own guide current.

- **The carrier** is the top-most member whose cached description has a `stack-review`
  block, readable or not, so a block that cannot be read is found and says why
  (`stack_guide_carrier`); a member added above it leaves the guide found, and out of
  date. The `stack` answer’s `guide` names it and its record revision while the stack is
  current, and is null otherwise, since a member not read yet may carry a block.
- **The route.** `guided-review?stack=<n>&step=<k>` (`stack_guided_review`) answers in
  the envelope a pull request’s guide has, naming the `stack`, its `carrier`, and the
  carrier’s page, `carrier_url`, which a note’s links are absolute against; the page
  reads a path-relative one as the file at the stack’s head.
  A stack this copy cannot pair is `stack_unavailable`, with the `stack` answer’s
  `reason`, and one with a member not read yet is `not_cached`; both come before the
  carrier is found, so they name no `record_revision`, and the page takes them as that
  step’s refusal. `left`, `right`, and `key` name the comparison to read at, as
  `stack-comparison` takes them: the current pair, or one the `stack` route gave before
  and keeps (`retained_stack_pair`); one it never gave is `stack_moved`, and kept pairs
  that cannot be read now are `stack_unavailable` with `snapshot_unavailable`. Without
  them the route reads at the current pair.
  A kept pair the guide’s pins are past, the current pair’s or a head after the kept
  one, is `stack_moved` too (`_pinned_past`): the carrier moved and its author pinned
  the guide again, so it was written for a later comparison, and read at the kept pair
  it would be reported rewritten.
  The guide’s pins are the stack’s base and top head; its `{path}` references read that
  pair’s kept manifest (`combined` in `pull_stack.py`), each step’s address is the file
  in the stack page’s Changes, and `_staleness` compares the pins with that pair, a
  member’s newer known head counting as a newer head at the current pair alone.
  `{pull}`, `{pull, path}`, and `{commit}` references read as in a pull request’s guide,
  the carrier’s stack first for a `{pull}`’s place.
- **The page.** `stack-page.js` mounts `mountGuidedReview` with no introduction: the
  description that carries the guide introduces its member, not the stack, so the
  navigation starts at step 1 (`first` in `createGuideNavigation`), and the refusals
  speak of the stack (`STACK_MESSAGES` in `guided-review.js`). The guide is read at the
  comparison the page draws, so it shows what the Diff summary, Docs, and Changes show,
  and follows the offer and take they follow: it is mounted again only when the reader
  takes the comparison offered.
  The guide shown stays while the stack is pending or cannot be shown, as the drawn
  comparison does (`guideShown`), and a step read then says so in its place, under the
  guide’s steps. A new revision of the carrier’s record is read in place while the
  comparison drawn is the current one.
  While it is not, the navigation is held at the revision read there (`behind` in
  `createGuideNavigation`): a step answer for another revision, which the carrier moving
  with the stack gives, is that step’s `stack_moved`, never a new guide, and the guide’s
  steps stay. A whole document a step cites is drawn from the comparison the page drew
  while that is the one the step was read at.
  `tests/dom/github-stack-guide-mount-session.js` runs this glue on the production page.
- **The member’s page.** `render_part` leaves a block that reads as a stack’s guide out
  of the description, as it leaves a guide’s, and Conversation puts a card in its place
  that says it has a stack guide, not the stack’s, since a member above may carry the
  one the stack shows, and links the page of each stack the pull request belongs to once
  the stacks are known (`STACK_GUIDE_FENCE` in `pull-page.js`, a hint as `GUIDED_FENCE`
  is).
- **The command line.** `--show /stack/<n>` reports `guide=#<member>` and the tab the
  front page shows.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
