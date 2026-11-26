# Mirror Acquisition and Refresh

**Status:** Built: acquisition of `file://` and `https://` sources into a full store or
an overlay that borrows a named checkout’s objects, the `gh` credential helper for
github.com, clone progress, background refresh with typed outcomes, pin switching and
ref listing, and explicit object recovery.
Not built: SSH transport, which the root-argument grammar classifies and acquisition
refuses, and converting a store between full and overlay, which the
[pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md#conversions)
leaves to future work.

A **mirror** is a published repository store and the source alias that names it, kept
current from its origin.
A served mirror answers every page from its store, so the origin can be unreachable and
the pinned revision still serves; network work happens only in acquisition and in
background refresh jobs.
The layout, records, and locks are in [Repository Cache](arch-repository-cache.md); what
a pinned revision serves, and the guard that keeps a page on its commit, are in
[Source Sessions and Pins](arch-source-sessions-and-pins.md).

## Transports and Credentials

An argument that names an existing path is a local path and never a source, unless it
starts with `scheme://`; today it opens the folder named, and
[Open Modes](arch-open-modes.md#resolving-a-target-to-a-root) designs opening its
repository’s root. Anything else goes to `classify_root_argument` in `cache/urls.py`,
whose grammar is frozen in `tests/fixtures/repository-cache/url-grammar.json`; a bare
path is never rewritten into a `file://` source.
An argument that names nothing on disk and begins with a host a reducer claims, such as
`github.com/owner/repo`, is given `https://` before it is classified (`_root_in_full` in
`cli/main.py`). Provider reducers run first (`cache/providers.py`); core names no
provider, and the GitHub reducer in `builtin_plugins/github/urls.py` turns web, raw, and
SSH spellings of a github.com repository into its canonical `https://` source plus a
selection. `file://` and `https://` sources are acquired; SSH is classified and refused.

A new acquisition needs a Git at or above the acquisition security floor
(`ACQUISITION_MINIMUM` and `ACQUISITION_PATCHED_TRACKS` in `git/process.py`, frozen in
`tests/fixtures/repository-cache/git-version-gates.json`). A source already in the cache
is reused under any Git.

`cache/origin.py` builds the two commands that acquisition and refresh run against an
origin: `ls-remote --symref` to learn which branch the origin’s `HEAD` names, then one
fetch of every branch and tag with explicit refspecs (`MIRROR_REFSPECS`). Both name the
origin by URL and get `origin_git_args`: a protocol allowlist of `file` and `https`, the
low-speed stall bound (`HTTP_LOW_SPEED_LIMIT_BYTES` for `HTTP_LOW_SPEED_TIME_S`), and
whatever the provider adds for that URL. Curl’s stall bound does not cover a TLS
handshake that never completes, so the first command against an `https` origin has its
own deadline (`REMOTE_PROBE_TIMEOUT_S`); the fetch has only `GIT_ACQUISITION_TIMEOUT_S`,
so a clone that keeps making progress is not stopped for taking long.
`classify_remote_failure` turns Git’s text, which is only logged, into a
`RemoteFailureState` a reader can act on.
A third command talks to an origin outside acquisition and refresh: the pull-request ref
fetch in `cache/pull_refs.py`, which [object recovery](#object-recovery) also uses, and
which gets the same `origin_git_args`.

Credentials belong to the provider:

- The GitHub provider sets `gh` as Git’s only credential helper, scoped to
  `https://github.com`, after clearing every configured helper
  (`builtin_plugins/github/provider.py`). Git asks a helper only after a server
  challenge, so public repositories stay anonymous.
  Metabrowser never reads or stores a token.
- Acquisition and refresh run Git with `HOME=/dev/null`, because curl reads
  `$HOME/.netrc` and Git cannot turn that off; only the `gh` helper command is given the
  real home, with the `GH_*` variables that would redirect or log it cleared.
- Acquisition never inherits a checkout’s remote or credential helper.
- `check_first_clone` (`cache/providers.py`) refuses every first clone, whatever its
  source, when the cache’s volume has less than the reserve free (`cache/free_space.py`,
  which `METABROWSER_CACHE_RESERVE_MB` sets).
  A first clone that borrows a checkout’s objects is not checked.
- With `gh` installed, the GitHub provider then refuses a first clone whose
  GitHub-reported size, packed, would leave less than the reserve free.
  It first runs
  [the GitHub status check](arch-github-pull-requests.md#the-github-status-check), and
  refuses a pull-request URL that `gh` is missing, too old, or not signed in to read.

Every fetch runs under `ACQUISITION_POLICY`, in the isolated Git environment of
`git/process.py`: no inherited `GIT_*` variable, no system or global configuration,
prompts and hooks off, and its own process group, so a timeout, Ctrl-C, a hangup, or
`SIGTERM` also kills the helpers it forked.
A serving refresh’s Git is outside the terminal’s foreground group, so the server takes
a hangup as it takes Ctrl-C: it kills the live process groups and exits.

Ref names resolve by exact, case-sensitive match (`cache/resolve.py`). A
case-insensitive file system cannot hold two refs that differ only in letter case, so
acquisition refuses such an origin as `ref_case_collision` rather than publish one ref
under the other’s commit.

## Acquisition

`acquire_source` in `cache/acquire.py` reuses a healthy published store whatever its
mode, an overlay with its remembered lender included, so a URL never silently changes
storage.
On a miss it fetches every object into a full store, or into an overlay when the
reader named a checkout with `--checkout`.

A cold open first takes the source acquisition reservation
(`locks/sources/<source key>.acquire.lock`), after the provider’s first-clone check.
Opens of other sources run concurrently.
A second opener of the same source tells its caller once that it is waiting, retries
without blocking the event loop, looks for the published store when it gets the
reservation, and gives up after `RESERVATION_WAIT_S` with an error that names the lock
file. Staging writers inherit the staging entry’s liveness descriptor but not the
reservation, so a killed owner’s orphaned fetch, which can never publish, keeps no one
waiting. A warm open reads the published store and takes no reservation.

The machine below is the design `cache/acquire.py` follows.
The code does not report these transitions, so no test replays the table; each path is
tested directly, as the paragraph after it says.

| From | Event | To | Locks held | Effect |
| --- | --- | --- | --- | --- |
| `absent` | `claim_staging` | `staging_claimed` | staging entry | Take `locks/staging/<entry>.lock`, then create `staging/<entry>/` |
| `staging_claimed` | `lookup_remote_head` | `head_observed` | staging entry | `ls-remote --symref` records the default branch and its commit |
| `staging_claimed` | `remote_unavailable` | `abandoned` | staging entry | Typed failure; staging deleted |
| `head_observed` | `fetch_started` | `fetching` | staging entry | `init --bare --template=`, Metabrowser’s configuration, then the fetch; an overlay first adds its configuration, alternates, and boundary link, and the fetch its negotiation tips |
| `fetching` | `fetch_failed` or `cancelled` | `abandoned` | staging entry | Git’s process group is killed; staging deleted |
| `fetching` | `fetch_succeeded` | `fetched` | staging entry | Objects are in the staging store or, for an overlay, its lender |
| `fetched` | `validation_failed` | `abandoned` | staging entry | The default branch or object format did not validate; staging deleted |
| `fetched` | `validated` | `validated` | staging entry | Write `store.yml`, with the lender if any, and `state.yml` |
| `validated` | `publish_store` | `store_published` | alias, store, staging entry | Verify the store directory is absent and rename staging into `repos/<store key>` |
| `validated` | `store_exists_same_identity` | `store_reused` | alias, store, staging entry | A concurrent acquisition published the same store first; staging is deleted after the locks are released |
| `store_published` or `store_reused` | `publish_alias` | `alias_published` | alias, store, staging entry | Create `sources/<slug>/` with `source.yml` and `store-alias.yml`, the only visibility commit |
| `store_published` or `store_reused` | `alias_exists_same_store` | `alias_published` | alias, store, staging entry | Another process committed the same alias first |
| `store_published` or `store_reused` | `alias_points_elsewhere` | `alias_conflict_reported` | alias, store, staging entry | The existing alias stays, and the new store is left unreferenced |

`tests/test_cache_publish.py` records the locks the real acquisition holds at the store
rename, the alias write, and the source rename.
`cli-cache-interrupt-store.txt` and `cli-cache-interrupt-alias.txt` kill a process
before each publication and show what the next acquisition finds, and
`cli-cache-fetch-failures.txt` shows the abandoned paths.
An interrupted acquisition leaves nothing visible, because the source is published last.

### Clone Progress

A first clone can run for minutes, so every mode that clones says on stderr where the
clone goes, how far it has got, and when it is done (`cli/clone_report.py`).
`git/progress.py` reads `git fetch --progress` and hands over only numbers; no text Git
or the origin wrote reaches the terminal, and a line of Git’s output that is not exactly
a progress record is dropped.
On a terminal the progress is one status line redrawn in place, and anywhere else a
whole line every `LOG_INTERVAL_S`. A line that cannot be written at once is dropped
rather than waited for, because the same event loop enforces Git’s deadline and delivers
a cancellation. Serve mode and `--no-serve` say in one line when the source was already
cached; `--show`, `--api`, and `--check-api` say nothing for a cache hit, since a script
runs them many times and `/api/source/status` reports the last fetch as data.

## The Lending Checkout

An **overlay** store’s `objects/info/alternates` names the objects directory of a
checkout the reader named, so the fetch brings only what that checkout lacks.
`cache/lender.py` reads the checkout and `cache/acquire.py` fills the store.
Every reader of a store is the same for both modes: the served pin, the batch readers,
`pull_refs.py`, `update.py`, the freshness window, the fetch lock, and the pull-request
records. The design and its experiments are in the
[pull-request review plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md),
and what borrowing means for content trust is in
[Borrowed Objects](arch-server-and-content.md#borrowed-objects).

- **Only a checkout the reader names lends.** `--checkout` names it once, and the store
  remembers it. Any directory a reader stands in can be made to look like a checkout of
  any repository, and Git does not verify an object’s hash on read, so the working
  directory never grants borrowing; when it is a matching checkout, a fresh acquisition
  prints the command that would have borrowed from it.
- **No Git runs in the checkout, and nothing writes to it.** Its `.git` pointer,
  `commondir`, configuration, and refs are read as bounded regular files.
  Its hooks, `core.fsmonitor`, `core.sshCommand`, and diff drivers are never consulted.
- **A remote must name the source.** Any remote counts whose URL, read through the same
  grammar and provider reducers as the command line, is the source; a remote spelled as
  a path is the `file://` source of that path.
- **The store’s refs are only what the origin sent.** Nothing is seeded from the
  checkout. Each tip of its remote-tracking refs that the store reads as a commit is a
  `--negotiation-tip`, up to `MAX_NEGOTIATION_TIPS`, recomputed before every fetch
  because a tip the checkout has lost makes Git refuse.
- **Two more configuration keys** (`_OVERLAY_CONFIG` in `cache/acquire.py`):
  `core.commitGraph=false`, or the store reads the lender’s possibly stale commit-graph,
  and `core.alternateRefsCommand=true`, or Git runs `for-each-ref` in the lender on each
  fetch.
- **The shallow boundary is live until the store must write it.** The store’s `shallow`
  is a symbolic link to the lender’s, so history stops where the checkout’s does and
  follows it when it deepens.
  Git locks the link’s target when it writes `shallow`, so `own_boundary` replaces the
  link with a copy, under the fetch lock, before any command that writes the boundary.
- **A dangling ref is swept.** A ref whose object the lender has collected wedges a
  fetch. Before each fetch into an overlay, under the fetch lock, `sweep_dangling_refs`
  deletes such refs; a ref the origin still has comes back with the fetch.
  Git answers `missing` alike for an object the lender collected and one it cannot lend
  now, so a ref is deleted only when `collection_doubt` finds no loose file of the
  object and every pack file of the lender readable; otherwise nothing is deleted and
  the fetch is refused as `lender_missing`.
- **The record and the file agree.** `store.yml`’s optional `lender` names the objects
  directory, the checkout, and the remote; absent means full.
  A record and alternates file that disagree is `damaged`.
- **A lender that has gone is refused at open,** with the recorded path and the repair,
  `--checkout <new path>`, which runs the same checks and finishes a repair that stopped
  before its record was written.
  The checks run again on every open and before every fetch.
  A refresh in a running server reports `lender_missing`, a read of a borrowed object
  answers `object_unavailable`, and the cache routes, which read records and no object,
  still answer.

What happens when a reader names a checkout:

| Situation | What `metab` does |
| --- | --- |
| No remote of the checkout names the source | Refuses, naming the repositories its remotes point at, with credentials left out |
| The path is no checkout | Refuses, whether or not a mirror of the source is cached |
| A partial clone, or a checkout with its own `objects/info/alternates` | Says why and clones a full store: the first would find objects missing on read, and the second would follow a chain nothing recorded |
| Another object format, unreadable objects, or objects another user owns | Says why and clones a full store |
| A shallow checkout | Lends; history views stop at its boundary, `shallow` is true, and every comparison runs the [merge-base certainty check](arch-github-pull-requests.md#comparisons) |
| A full store of the source is already cached | Keeps it, says so, and borrows nothing; no command converts one |
| The store already borrows from another checkout that can still lend | Keeps that lender and says so |
| The route is under `/api/cache/` | Says the flag is not applied to a cache route and answers it |

Beside a served folder, core acquires an overlay with the folder’s checkout as the
lender, never falling back to a full clone (`acquire_checkout_store` in
`checkout_store.py`). A folder’s server makes it to list its origin’s branches and tags
([Origin Branches in a Repository Folder](arch-open-modes.md#origin-branches-in-a-repository-folder)),
and the GitHub plugin asks core for the same store for a pull request’s comparison.
A served subdirectory resolves to its enclosing checkout first, and the lender’s path
stays in private cache metadata.
[GitHub Pull Requests](arch-github-pull-requests.md#beside-a-checkout) covers when it
runs.

## Refresh

`update_store` in `cache/update.py` refreshes a published store with one plain fetch,
since a store is a read-only mirror:

1. Try the store’s fetch lock without blocking.
   Busy means a live refresh here or in another process, reported as
   `refreshing_elsewhere`, never waited on.
2. Remove the lock files, temporary objects, and temporary packs a killed Git left in
   the store (`remove_interrupted_fetch_leftovers`); every writer holds the lock, so
   none is live.
3. `ls-remote --symref` the origin, then `fetch --prune --atomic --no-write-fetch-head`
   every branch and tag, so every ref moves together or none does, a branch or tag
   deleted upstream leaves the mirror, and no commit is removed.
4. If the atomic fetch fails, prune the stale refs on their own and try once more.
   One transaction cannot delete `side` and create `side/x`, or rename `Topic` to
   `topic` on a case-insensitive file system, and Git words that refusal differently for
   loose refs, packed refs, and reftable.
5. On a case-insensitive file system, list the refs before the fetch and check after it
   that no ref was folded into its case twin (`folded_refs` in `cache/resolve.py`),
   because there Git can succeed wrongly.
   A fold, or a clash the retry still meets, puts every ref back and is
   `ref_case_collision`; the check and any restore run to the end even when cancelled.
6. Take the store lock only to rewrite `state.yml`.

Every failure is a `RefreshOutcome`, whose members are documented in `cache/update.py`;
nothing raises into a caller for what the origin or the network did.

| From | Event | To | Locks held | Effect |
| --- | --- | --- | --- | --- |
| `published` | `take_fetch_lock` | `fetch_locked` | fetch | Lock taken without blocking |
| `published` | `fetch_lock_busy` | `refreshing_elsewhere` | none | Fetch nothing |
| `fetch_locked` | `remove_stale_locks` | `locks_cleaned` | fetch | Leftovers of a killed Git removed |
| `locks_cleaned` | `lookup_remote_head` | `head_observed` | fetch | The origin’s `HEAD` branch recorded |
| `locks_cleaned` | `remote_unavailable` | `failure_recorded` | fetch, store | `state.yml` records the failure and keeps the previous fetch |
| `head_observed` | `fetch_started` | `fetching` | fetch | The atomic fetch, in Git’s own process group |
| `fetching` | `fetch_refused` | `pruning` | fetch | Git ran and failed, and no ref moved |
| `fetching` | `fetch_failed` | `failure_recorded` | fetch, store | Git could not start or hit its deadline |
| `fetching`, `pruning`, or `refetching` | `cancelled` | `cancelled` | fetch | Git’s process group is killed; refs are whole, and the record is unchanged |
| `pruning` | `stale_refs_pruned` | `refetching` | fetch | `git remote prune` with the mirror refspecs, then the atomic fetch again |
| `pruning` or `refetching` | `prune_failed` or `fetch_failed` | `failure_recorded` | fetch, store | The record keeps a default branch the mirror still has |
| `fetching` or `refetching` | `fetch_succeeded` | `fetched` | fetch | Every branch and tag moved together |
| `fetched` | `validation_failed` | `failure_recorded` | fetch, store | The default branch is missing or not a commit |
| `fetched` | `record_written` | `recorded` | fetch, store | `state.yml` gets the default branch, its commit, and the fetch time |

`tests/test_cache_update.py` drives each path against a real mirror, and
`cli-git-refresh.txt` pins a refresh through the CLI.

### After a Crash

| State at the crash | What the next run finds |
| --- | --- |
| Any acquisition state before `store_published` | The startup sweep finds the staging entry’s lock free and deletes it. A killed clone leaves files behind, so staging is never inside a published path |
| `store_published` or `store_reused` | A store no alias names, kept and reused by the next acquisition of the source |
| `fetching` or `refetching` | Refs moved together or not at all; the next refresh removes the leftovers under the fetch lock, which it can take only once no Git of the interrupted refresh is alive |
| `pruning` | Some stale refs are gone and others are not; the next refresh prunes the rest |
| `fetched` | Refs moved but `state.yml` names the previous fetch; nothing reads the record to find a commit, and the next refresh rewrites it |
| Any other | Nothing durable changed |

## Refresh Cadence

A served mirror answers every page from the store and never makes a request wait on the
network (`mirror_refresh.py`). A mirror is stale once its last fetch is older than
`FRESHNESS_WINDOW_S`.

A store Metabrowser keeps is fetched as often as it usefully can be (the owner’s rule,
2026-11-22): a fetch into it is atomic, removes no commit, writes no reader’s checkout
([What Is Never Written](arch-open-modes.md#what-is-never-written)), and spends no
GitHub rate limit, so what limits it is process time and network.
Three cadences follow, each constant beside its measurement in `mirror_refresh.py`: a
visible page on a branch has that branch probed every `STORE_PROBE_S`, a visible page
has the whole mirror fetched once it is older than `FRESHNESS_WINDOW_S`, and a server no
page is looking at fetches every `STORE_IDLE_REFRESH_S`. The same three hold for the
store a repository folder keeps of its checkout’s origin
([Origin Branches in a Repository Folder](arch-open-modes.md#origin-branches-in-a-repository-folder)):
`StoreSession` is the store’s half of the session, which reads no served subject, and
`MirrorSession` adds the pin.

- **The coordinator:** `RefreshCoordinator`, on the application state, keeps one job per
  key, a store key or a store key and a pull-request number, so concurrent requests join
  the running one; `MAX_CONCURRENT_REFRESHES` bounds the network jobs across every key.
  A job outlives the request that started it, and its failures are typed outcomes.
  Graceful shutdown cancels the jobs, which kills their Git; Ctrl-C kills the process
  groups and exits at once.
- **Turns at the store:** within one server, jobs that fetch into the store take turns
  (`StoreTurn`) before its fetch lock, so none finds another holding it.
  The mirror’s fetch and the attended pull request’s go first, since a page of code
  waits on them, at most `MAX_FIRST_IN_A_ROW` ahead of a waiting job; background work
  goes only when nothing else waits and is cancelled when something starts waiting.
  A job takes its network slot only once its turn has come.
- **When a refresh starts:** serve mode refreshes a stale mirror once at startup, and a
  page asks for one when it opens or becomes visible on a stale mirror.
  A visible pull request’s page asks more often, and its server probes GitHub between
  full reads
  ([Serving Pull Requests](arch-github-pull-requests.md#serving-pull-requests)). A
  refresh that moves the served branch moves the pin with it
  ([Following a Branch](#following-a-branch)). When another process holds the fetch
  lock, a served mirror follows that refresh (`ELSEWHERE_POLL_S`, up to
  `ELSEWHERE_WAIT_S`) and observes the store when it ends.
- **A visible page on a branch:** the status names `probe_every_s` for a pin served
  under one of the origin’s branches (`probes_origin`), and the page sends its own ask
  that often while it is visible, `POST /api/source/refresh` with `{"for": "page"}`,
  starting with its first status, so a hidden page sends none
  (`MirrorSession.page_ask`). The ask answers the status, so it is the page’s poll too.
  The server fetches the whole mirror when it is older than the freshness window.
  Otherwise it probes: one `ls-remote` of that branch (`StoreMirror.origin_tip`), which
  takes no turn at the store, no network slot, and no lock, since it writes nothing.
  A tip that differs from the mirror’s starts the fetch at once, so a push is served a
  few seconds later and not a window and a poll later.
  The request waits for the probe at most `STORE_PROBE_WAIT_S` and never for a fetch.
  Core probes with Git alone and knows no provider.
  A tag, a commit opened by its ID that no branch names, and a pull request’s head are
  not probed.
- **A visible page on a repository folder’s own branch:** such a page sends the same
  ask, every `CHECKOUT_REFS_POLL_S`, for the server to read where the branch is in the
  checkout
  ([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)).
  Where the folder keeps a store of its origin the ask is the store’s too, so while that
  page is visible the store is fetched, quietly, once it is older than the freshness
  window, and not only once for each time the page is shown.
  That follows the rule for Metabrowser’s own stores: they are fetched as often as is
  useful, and the checkout is never fetched into.
- **What holds a probe or a page’s fetch:** one probe runs at a time, no closer than
  `STORE_PROBE_FLOOR_S` to the last, however many tabs ask, and none while a refresh
  runs. A probe that failed, or a fetch that failed, holds the page’s asks for a
  freshness window from when it failed, so an origin that is gone or a machine that is
  offline is asked once a window; a reader’s own Refresh is never held.
  A tip a probe started a fetch for starts no second one within a window once that fetch
  ran to the end, so an origin whose fetch does not bring what its `ls-remote` names
  cannot make every probe a fetch.
  A fetch that did not run, or one the probe only joined, holds nothing, so the next
  probe fetches for the tip.
- **A fetch nobody asked for is quiet:** the fetch a page’s ask starts once a window,
  and the idle one below, run with no reader waiting, so status reports them with
  `refresh_quiet`, and the row repaints nothing: no “Refreshing…”, no disabled button,
  and nothing announced.
  A reader’s own Refresh that joins one ends its quiet.
  The fetch a probe starts because the branch moved is one the page asked for, and shows
  as a refresh.
- **A server no page is looking at:** `MirrorSession.run_idle_refresh`, started by the
  lifespan in serve mode only, fetches once the last fetch, by this process or another
  as the store’s record has it, is older than `STORE_IDLE_REFRESH_S`. It is the one
  timer a server runs for a mirror, and a visible page’s asks keep the mirror newer than
  it looks for. The record is read again when the fetch comes due, so another process’s
  fetch is followed, and the served branch with it, instead of repeated.
  The fetch is background work at the store: it goes only when no other job waits, takes
  no network slot, and is cancelled when a reader’s job starts waiting, to be tried
  again a freshness window later.
  Status does not report that as a cancelled refresh, since no reader asked for it.
  A reader’s refresh, a page’s ask, or a waiting URL selection that joins it makes it
  theirs: it stops being background work, and `StoreTurn.promoted` stops any background
  job holding the turn ahead of it, as a reader’s job arriving would have.
  One that joins after the fetch was told to stop, before the cancellation is delivered,
  has the fetch started again as its own once the stopped one has unwound
  (`MirrorSession._join_running` asks `RefreshCoordinator.start_again_when_stopped`,
  which restarts a prefetched pull request’s job the same way).
  One that failed is tried again only after the whole interval.
- **A commit the mirror lacks:** a page that opens a commit’s address asks for the fetch
  it waits on, which runs only when the mirror is stale, since a link in served content
  can lead to any address; a reader’s **Retry** always fetches.
- **A selection the mirror lacks:** in a server, a pin request or URL selection the
  store lacks answers pending, starts one background fetch, and is remembered until that
  fetch ends (`MAX_REMEMBERED_MISSES`); a URL selection is served when the fetch brings
  it. A one-shot command reads the mirror as it is and reports the selection not found.
- **One-shot commands:** startup may acquire the source and fetch pull-request data or
  refs the URL needs; after that, reads never fetch, and only an explicit refresh route
  does, waiting for its job.

`MirrorSession` answers the freshness fields of the status route from memory, observing
the pinned ref’s tip again when a job finishes and when the pin changes, so polling runs
no Git and reads no store.
A valid pin opens without network access, and a failed refresh leaves the served
revision as it was. A cached source whose pinned tree has gone from the store reports a
path-free error when the pin is opened, with no traceback and no automatic clone;
startup starts no repair fetch.

### Following a Branch

A mirror is browsed as github.com is: as of the data last fetched.
A reader who opened a branch, a tag, or a pull request reads that ref, not one commit of
it, so the served pin follows the ref when a fetch moves it, by a push or a force-push.
The owner set this on 2026-11-19, replacing the earlier rule that a refresh never moved
the served commit and offered the new one behind a **Switch** button (bead `mb-pq8y`),
and on 2026-11-22 for a pull request’s head (bead `mb-6a6w`).

- **Which pins follow:** one asked for by the origin’s branch, a tag, or a pull
  request’s head, `refs/pull/<n>/head` (`follows_moves` in `mirror_refresh.py`), by name
  or as `under`, which status reports as `follows`. A commit opened by its ID stays put,
  as the owner decided (bead `mb-cww9`): it is served under no ref, or named by one
  whose tip it is, the ref last served, as View file’s way back is, or a pull request’s
  head, so the selector names that ref, but it never moves with it
  (`MirrorSession._by_id`), and a pull request it heads is not attended.
  When that ref moves on, status reports its tip as `latest`, and the row offers it,
  `<ref> is now at <commit>` with **Switch**, which asks for the ref by name.
  A pull request’s head moves in the mirror when that pull request’s refresh fetches it,
  so the job that refreshes a pull request observes the mirror when it ends, as a fetch
  of the mirror does.
- **The server follows:** `MirrorSession.observe`, which runs after every refresh job
  and after following another process’s, opens the ref’s new tip under the pin lock and
  serves it under a new generation.
  A pull request’s record that another process published reaches this server only when
  its pull route reads it, so a read whose record names another head than a pin on that
  pull request’s head starts one observation (`follow_adopted_head` in
  `builtin_plugins/github/pull_route.py`, `MirrorSession.observe_pull_head`). So the
  server never serves a branch behind where the mirror has it, a page or none open, and
  Files and the Commits tab, which walks the served commit’s history, agree.
  A ref the origin deleted is not followed; its last commit stays served, and the row
  says the ref is gone.
- **The page follows:** `static/source-freshness.js` sees on its next poll that the ref
  it was drawn for is served at another commit.
  It asks the pin route for that ref with its own `/view/` address, which changes
  nothing once the server has followed and serves the tip when it could not yet, and the
  answer’s `view_href` says where the page lands: the same file or folder when the new
  commit has it, where the page reloads in place and keeps its line and scroll, or the
  root. A pull request’s page reloads where it is; its Changes then shows the new head’s
  diff, says which head it showed before, and holds the reader’s place in its file
  ([Changes Follows the Head](arch-github-pull-requests.md#changes-follows-the-head)). A
  refused follow says why and offers a reload, and is not asked again until the reader’s
  refresh.
- **A switch made in another tab** to another ref still only offers a reload: the reader
  did not ask for that ref.
- **A repository folder’s own branches** follow by the same step and the same page code,
  with the move read from the checkout’s refs in place of a fetch
  ([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)).
  There a commit opened by its ID alone never follows, even while it is served under the
  tip of the ref last served (bead `mb-dna1`).

## Source Routes

Each handler’s docstring in `source_routes.py` holds its contract; the route index is in
[Views, Models, and Routes](arch-views-models-routes.md).

- **`GET /api/source/status`** is `SourceStatus` in `source_routes.py`, whose freshness
  fields are `FreshnessFields` in `mirror_refresh.py`: the pin, the ref it was resolved
  from, the mirror’s name, origin, location, lender, and boundary, its freshness, the
  attended pull request, and a pending URL selection’s state.
  It sends an ETag and answers `If-None-Match` with `304`.
- **`POST /api/source/refresh`** starts or joins a refresh and answers at once.
  `{"for": "commit"}` is the fetch a missing commit waits on, fetched only outside the
  freshness window unless `"retry": true`; its `pull_refresh` says how the attended pull
  request’s refresh was answered.
- **`GET /api/source/refs`** lists every one of the mirror’s branches or tags for the
  ref selector from one `for-each-ref`, filtered by name (`REFS_MAX_QUERY_CHARS`), each
  with its commit and that commit’s committer date, from which the selector shows its
  age. The default branch lists first, then the rest newest first by that date, then by
  name (`_newest_first` in `cache/resolve.py`); nothing pages the list, and the measured
  cost of listing every ref is beside the constants in `source_routes.py`. An answer the
  Git routes’ memo can keep is kept under the store’s ref state and the recorded default
  branch (`_refs_answer_key`), so asking again while no ref moved runs no Git.
  The memo keeps no body over its `MAX_ENTRY_BYTES`, about 9,000 branches, or about
  5,200 where each is a pull request’s head (`REF_PULLS_PER_ROW` in `source_routes.py`),
  and has no key for a repository with more loose refs than `MAX_REF_ENTRIES`; a listing
  of either runs Git every time.
  A folder that is a repository’s root answers it and the pin route for its own
  checkout;
  [Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)
  says how.
- **`POST /api/source/pin`** resolves a branch, then a tag, then a commit ID in the
  mirror, never through revision syntax, and serves it under a new generation.
  With the page’s `/view/` address it answers `view_href`, where that page goes on the
  new pin. Its refusals are the `SelectionError` subclasses in `mirror_refresh.py`. A
  commit pinned by ID is served under the ref last served, or a pull request’s head ref,
  the first whose tip it is, and stays put there.
  A request may name the ref as `under`, as View on branch and Browse code name the pull
  request’s `refs/pull/<n>/head`; when that ref is not at the commit, because the pull
  request moved on after the page was drawn, nothing is switched and the answer is
  `409 ref_moved`.

The two POST routes change state or start work, so each takes a JSON body behind the
application’s same-origin guard, and a link inside a served page cannot reach them.
A folder, or a pin with no mirror, answers `unsupported_for_subject`.
[Open Modes](arch-open-modes.md#views) designs `/api/source/refs` and `/api/source/pin`
for a repository folder, whose listing adds its remote-tracking branches and its working
tree; a plain folder keeps this refusal, and no folder is ever refreshed.
`tests/test_source_refresh.py`, `tests/test_mirror_companion.py`, and
`tests/test_github_serve.py` cover a server; `cli-api-source.tryscript.md` and
`cli-github-url-waits.txt` pin the routes through the CLI.

### What a Mirror’s Page Is Called

A served mirror’s page is headed as a folder’s is, by a name, with the place it is kept
in sight:

- **Name:** the repository’s name as `git clone` would name its directory, the last
  segment of the origin’s address without `/.git` or `.git` (`repository_name` in
  `cache/served_mirror.py`). The GitHub URL reducer lowercases owner and repository so
  every spelling shares one mirror, so a GitHub repository is named in lowercase.
  A pin with no mirror is headed by its ref and commit.
- **Title:** `/api/identity` gives the tab and window title, and a `full_name` of the
  origin without its scheme and the pin, which never names the cache.
- **Commit:** the navigation heading shows the name.
  The revision row below the Files and Commits tabs names the ref.
  Its chip opens the ref’s actions, and the separate chevron opens the chooser, whose
  list shows short commit IDs.
- **Location:** the Info menu shows the local path to the bare repository with a short
  source note. A separate note after the address shows the store directory.
  Both abbreviate the home directory as `~` (`display_directory`).
  `static/mirror-heading.js` draws the address note from data in the mirror’s page.

An origin is untrusted: its name is display text that passes through `display_segment`,
is cut when too long, and is escaped on the server and again in the page.

The status route (`SourceStatus` in `source_routes.py`) answers `name`, `origin`,
`location`, `borrows`, and `shallow`. `location` is the one field of any route’s answer
that names a path in the cache, and `borrows` names the checkout a mirror borrows
objects from, under the same exception; no route accepts either back.
The shell writes the same text into the navigation heading’s `data-mirror-location` and
`data-mirror-tip` attributes.
`tests/test_serve_pin.py` fails if the application home, the origin’s path, the store’s
key, or the stores’ directory appears anywhere else in a served mirror’s bodies and
headers. Repository content cannot read the location: Markdown and pull-request text
reach the page only as the inert allowlist, and the page’s Content-Security-Policy runs
no script and loads no stylesheet a repository supplies
([the content-trust model](arch-server-and-content.md#content-trust-model)).

## Object Recovery

A borrowed object can disappear when its lender changes, and a fetch can leave a
descendant blob absent.
`cache/object_recovery.py` is an explicit recovery a reader asks for; no read or
automatic refresh calls it.
It checks the displayed commits and the object IDs `git/object_failures.py` observed
missing for that comparison, fetches the missing ones by ID under the fetch lock and the
sweep rules, and authenticates each complete recovered object before clearing its
observation, all within `RECOVERY_TIMEOUT_S`. Before declaring success it advances the
store reader pool’s generation, so no later read uses an unlinked pack.
A corrupt object the lender still claims to have stays a typed refusal, since fetch
negotiation cannot replace it, and an object the origin no longer serves is
`commits_unavailable`. The pull-request request that triggers it is in
[GitHub Pull Requests](arch-github-pull-requests.md#beside-a-checkout).

## Open Questions

- `FRESHNESS_WINDOW_S` was measured over `file://` only; its cost over `https://` is not
  measured.
- On a macOS store, an origin ref whose name is decomposed (NFD) lands on the first
  refresh, but `git remote prune` precomposes the name while `fetch --prune` does not,
  so a later refresh meets a ref-lock clash and reports `ref_case_collision`.
- Whether distribution Git builds that backport the security fixes under an older
  version string pass the acquisition floor is open in the
  [open-repo plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md#phase-0-decisions).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
