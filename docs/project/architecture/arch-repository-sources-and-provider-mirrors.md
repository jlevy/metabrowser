# Repository Sources and Provider Mirrors

**Superseded in part (2026-09-23):** planned fetch jobs, credential handling, and
provider mirrors below are replaced by
[Thin Mirror for Git and GitHub Browsing](../specs/active/plan-2026-09-23-v012-thin-mirror.md).
Revision leases, subject refs, convergence, and store reclamation are removed from the
code and from this document.

**Status:** Partly implemented.
Repository subjects, `SourceSession`, capabilities, the attached-filesystem content
source, `GitCommandTarget`, the immutable Git tree source with `GitPath` file, raw, and
tree routes, `file://` and `https://` acquisition into a shared, read-only repository
store, admitted checkout borrowing, and the GitHub URL reducer are implemented; `metab`
opens a pin in-process for `--show`, non-cache `--api`, and `--check-api`, at the commit
its URL selects, and serves it over HTTP under the forced untrusted profile.
Under that profile its Markdown renders inert, reduced to an allowlist of plain markup
on the server and again in the page, and the page carries a Content-Security-Policy; see
[SECURITY.md](../../../SECURITY.md#content-trust-model).
A served store refreshes from its origin in the background, and a server can switch its
pin to another branch, tag, or commit of the same store.
Pull-request records are implemented: a pull-request URL pins the pull request’s head,
and its record is served beside the mirror and refreshed with it.
The pull-request page is implemented in the GitHub plugin at `/pull/<n>`, and
[Thin Mirror for Git and GitHub Browsing](../specs/active/plan-2026-09-23-v012-thin-mirror.md)
replaces the planned parts of this document wherever they disagree.
It retired blobless clones and convergence, private subject refs, revision leases,
maintenance locks, fetch jobs, and credential leases; this document no longer describes
them.
Provider binding and local object-availability records are not built; their retired
design is in [Hosted Review Model and Provider Boundary](arch-hosted-review-model.md).
Per-seam state is in [Implementation Seams](#implementation-seams).

Metabrowser must be able to show the same hosted repository through several independent
sessions without switching a shared checkout or duplicating provider state.
A user-owned working tree, a repository opened from a URL, a pull request, and a future
repository switcher are different ways to select content; they are not different owners
of that content.

This document defines the boundary between browsed sources, cached Git data, and cached
provider resources. The general external-resource model is in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md).
The GitHub-first domain model is in
[Hosted Review Model and Provider Boundary](arch-hosted-review-model.md).

## Three Independent Layers

```text
session selection
  attached filesystem root OR immutable repository revision
                         │
                         ▼
shared repository store
  every Git object, mirrored branches and tags, tree indexes
                         │
                         ▼
shared provider mirror
  repository, PR, review, check, release, and index observations
```

The layers have separate identities and lifetimes:

- A **repository subject** says what one session is browsing.
  It is either a mutable filesystem root or an immutable
  `{repository_store_id, full_object_id}` revision.
- A **repository store** is a Metabrowser-owned, worktree-free Git object database.
  It is shared by every session and attachment that resolves to the same repository.
- A **provider mirror** is the immutable, authorization-scoped observation store for one
  stable hosted-repository identity.
  It is shared independently of local paths and Git clone URL spelling.

No layer owns either of the other two.
Closing a session does not delete a repository store.
Detaching a local checkout does not delete provider snapshots.
Purging a generic source alias cannot delete objects or snapshots still reachable
through another alias, current pointer, or archival pin.

## Repository Subjects

An attached filesystem root remains the authority for the Files view of a user-owned
checkout. That view includes local modifications and uses the existing watcher,
filesystem inventory, status, and safe-path behavior.
Metabrowser never fetches into, switches, resets, locks, or writes the checkout or its
`.git` directory when adding hosted functionality.

Branch, tag, commit, pull-request, and release-tag views use immutable repository
subjects. A moving ref is resolved once to a full object ID; the session descriptor
records both the requested label and resolved ID, and all tree, blob, history, and diff
reads use the full ID. Two sessions can therefore browse different branches of the same
repository concurrently without an index, checked-out branch, detached worktree, or
global root mutation.

The future repository switcher changes the active subject descriptor.
It does not move files, change refs, or create a new cache.
The v0.12 server and browser session have exactly one active subject; every route,
history session, plugin dispatch, cache key, and event stream is tied to that subject’s
generation. Switching the pin within one repository is such a change: the new subject is
attached under a new generation and the one it replaced is closed.
Separate Metabrowser processes may browse different subjects from the same store
concurrently. A later multi-subject server would require subject-qualified addresses and
per-request leases; this design does not imply that unsupported routing.

### Source session and content contract

`SourceSession` is the composition root for one active subject.
It owns:

- the `RepositorySubject` and opaque subject generation;
- its `ContentSource` and navigation/index provider;
- a `SourceCapabilities` envelope; and
- the subject’s readers, closed when the session closes.

Root replacement closes and joins the old `SourceSession` before publishing the new one.
Work from the old generation cannot update route caches, history sessions, browser
state, or event streams after replacement.

Filesystem and revision subjects share one application-level content-source contract,
not one invented filesystem representation:

- enumerate a directory with byte-safe names and stable ordering;
- inspect kind, mode, object identity, and bounded size;
- read a bounded byte window;
- resolve a child path without following an unsafe escape;
- state whether content is mutable and whether watchers, mtimes, ignore state, and local
  status are meaningful; and
- close all readers.

The existing filesystem inventory continues to provide filesystem-only facts.
An immutable Git-tree source enumerates trees and reads blobs directly from the
repository store.
It does not fabricate mtimes, writable paths, ignore status, or watcher
events. Routes and renderers consume the content-source handle selected for the session;
plugins never receive a cache path.

`SourceCapabilities` separately declares bounded content reads, filesystem paths,
recency, ignore state, watchers, activity events, writable paths, and Git targets.
An immutable Git tree supports content reads and a Git target but not filesystem paths,
mtimes, ignore state, watchers, activity events, or mutation.
A route or query that requires an absent capability returns a typed
`unsupported_for_subject` result or is omitted from the view registry; it never emits a
fake zero, empty event stream, or placeholder timestamp.
Size- and kind-based rollups remain available when their inputs exist.
Recency filters, `/api/recent`, `/api/activity`, `/api/stream`, and editing are
unavailable for immutable trees until a truthful source-specific model is added.

### Plugin content boundary

The Python plugin SDK exposes bounded operations over an opaque `ContentRef`:
`resolve_content`, `resolve_content_container`, `stat_content`, and
`read_content_window`, in `plugin_api.py`. A hook passes back the identity its client
holds — an inventory path under an attached folder, a `GitPath` wire on a pinned
revision — and never constructs one or branches on the subject kind.

- `resolve_content` answers `None` for every identity that names nothing readable:
  traversal out of the served root, a missing name, a directory or tree, an unusable
  symlink. `resolve_content_container` is the same answer for a `<content>/<inner>`
  address, scoped to the suffixes the calling container claims so one plugin cannot open
  another’s files. Both return the identity to echo back, the logical extension to
  dispatch on, and a fingerprint that changes exactly when the bytes can have, so a hook
  keys its own cache without knowing whether that is an mtime hash or a blob object id.
  They also return the stored size, a file’s size on disk or a blob’s length, which
  costs no read.

- `read_content_window` takes a required `max_bytes`; there is no unbounded variant, and
  the bound is on bytes, not on a decoded string.
  It reports whether content continues past the window, which is what settles size for a
  compressed artifact whose declared length is a trailer nothing verifies.
  On a pin a window streams the blob from its start, as a compressed artifact does, so
  reaching an offset costs reading up to it; only the window is held, and no blob is
  refused for its size.
  `stat_content` is the separate call for a caller that needs a validated logical size
  and accepts what establishing one costs.

- Every failure is one catchable family, `ContentReadError`, over the typed errors those
  layers already raise, carrying a `code` and an `http_status` a hook maps once.
  The statuses are the ones the pinned routes answer with, which
  `tests/test_plugin_content_reader.py` pins against `git_content_failure_response`.

`resolve_path`, `resolve_directory`, `relativize_path`, `served_root`, and
`open_content` remain filesystem-only with their existing behavior and raise
`UnsupportedSourceCapabilityError` on a subject with no filesystem root.
Plugin dispatch does not invoke a legacy path hook when the active source lacks
`filesystem_path`; the corresponding view is absent with a capability reason.
These calls are additive to the Python helper surface and leave the browser SDK contract
alone, so `PLUGIN_SDK_VERSION` does not move for them; a change to the existing
semantics would bump it and every built-in manifest in the same commit.

The source-boundary phase updates file and raw delivery, tree and rollup assembly,
container resolution, classification, KPress render/export, event routes, and the
binary, structured, agent-log, diff, image, and Markdown built-in hooks.
Built-ins use content references where they only need bytes and explicitly require a
filesystem path where their behavior genuinely depends on one; the four data hooks that
read blob or file bytes hold no Git import and no source-kind branch.
Plugins receive leased, bounded reader ports, never unrestricted `ContentSource` objects
or cache paths.

### What a mirror’s page is called, and where it says it is kept

A page of a served mirror is headed as a page of a folder is: by a name, with the place
it is kept in sight (decided 2026-10-01, `mb-fndz`). It used to show the full commit ID
where a folder shows its name, and nothing said its files came out of the cache.

- **Name.** The served root is called by the repository’s name, as a checkout of it
  would be: the rule `git clone` names its directory by.
  It is the last path segment of the origin’s address, without a trailing `/.git` and
  without a `.git` suffix, so `https://github.com/jlevy/squares`,
  `file:///srv/squares.git`, and `file:///srv/squares/.git` are all `squares`. An
  address whose path names nothing else is called by its host, and a segment that is
  only dots before `.git`, such as `..git`, keeps its suffix, since `.` is no name.
  One rule serves every `https://` and `file://` origin and a pull-request pin
  (`repository_name` in `cache/served_mirror.py`). The name stands in the navigation
  heading, as the dimmed root of the main heading’s address, and in the heading’s
  tooltip. A pin with no mirror has no origin to take a name from and is headed by its
  ref and commit, as before.
- **Commit.** The ref and the short commit follow the name in the navigation heading,
  and a control after the short commit copies the full one, through the SDK’s
  owner-stamped copy delegate.
  The full commit is also in the headings’ tooltips and in `/api/source/status`, and
  every data request of the page still names it.
- **An origin is untrusted.** The name is display text and never a path.
  A percent-escape is decoded, and the result passes through `display_segment`, so a
  control character, a character drawn as nothing, and bytes that are not UTF-8 become
  U+FFFD. A name longer than a directory can be called is cut with an ellipsis.
  The server escapes it as HTML and the page escapes it again where it writes it.
- **Location.** The page says where the mirror is kept, with the home directory as `~`
  when the application home is under it and absolute otherwise, as a served folder’s
  path is. The directory named is the store’s bare repository,
  `repository-stores/<store-key>/repository.git`, and not the source’s directory under
  `sources/<slug>`. That directory carries the repository’s name, but it holds a few
  small records and no Git object: its size is kilobytes and `git -C` fails there.
  The bare repository is what every page is read from, what the clone’s size is, and
  where `git -C <location> log --all` works.
  The name it lacks stands beside it.
- **No folder is implied.** Nothing is checked out: each file is read from a Git object
  at the pinned commit.
  So the location is not the start of the address, where it would read as a folder
  holding these files.
  It is a note after the address, and the tooltip on the name, on the note, and on the
  navigation heading says what the directory is:
  `Mirror of <origin> at <commit>, stored in <location>: a bare Git repository, with no checked-out files.`
  An overlay store’s adds `, borrowing objects from <checkout>` after the location, and
  `/api/source/status` has `borrows` beside `location` under the same exception, with
  `shallow`, true when the store has a boundary.
  The note is whole or absent: a pane too narrow for its start shows none of it, and it
  takes no width from the address.
- **Only a mirror’s page.** `static/mirror-heading.js` draws the note, the tooltip line,
  and the copy control.
  The server writes it inline into a served mirror’s page and into no other, as it does
  the pin guard, so a folder’s page carries none of it; the shell reaches it through one
  hook that returns nothing when the module is absent.
  Only the mirror’s line of a tooltip wraps; the tooltip every page uses is unchanged.

The stack kept every cache and store path out of every route’s answer.
That rule now has one exception, held to an exact form:

- **One model.** The status envelope (`SourceStatus` in `source_routes.py`) carries
  `name`, `origin`, and `location`, each null for a folder and for a pin with no mirror.
  `location` is the one field that names a path in the cache.
  It is answered wherever the envelope is: `GET /api/source/status`, and the `status`
  member of what `POST /api/source/pin` and `POST /api/source/refresh` answer.
  `origin` is the source’s address as the reader gave it, in display form: for a
  `file://` origin it is a path of theirs, shown with the home directory as `~` when it
  is under it (`file://~/git/squares.git`), by the same rule as the location.
  No answer spells the home directory out when it can be abbreviated.
  `metab --api` prints `location` as answered, the one field a pin’s output does not
  rewrite to `<ROOT>`.
- **One place on the page.** The shell writes the same text into two attributes of the
  navigation heading, `data-mirror-location` and `data-mirror-tip`, as it writes a
  folder’s path into `data-served-root`. `static/mirror-heading.js` reads them back.
- **Nothing else.** File content, listings, rollups, history, diffs, plugin hooks, and
  every error stay path-free; the `/api/cache/` routes still answer
  `unsupported_for_subject` on a served pin.
  The location is display text: no route accepts it, and no path is ever built from it.
- **Checked.** `tests/test_serve_pin.py` asks every registered GET route of a served
  mirror for its answers, error answers among them, and the two POST routes that change
  the served pin for each kind of answer they give.
  It fails if the application home, the origin’s path, the store’s key, or the name of
  the stores’ directory stands anywhere in a body or a header but those two fields and
  those two attributes, each compared to its exact text.

A served mirror is untrusted content, which is why the rule existed.
The location still cannot be read by what a repository’s author writes.
For it to leak, repository content would have to run script in the application’s origin,
or apply a stylesheet to the application page and report what a selector matched to
another host. Neither holds:

- Repository Markdown and pull-request text reach the page only as the inert allowlist,
  applied on the server and again in the page: no script, stylesheet, `style`, `class`,
  `id`, or `data-*` survives, so nothing in a document runs or selects the heading.
- The page’s Content-Security-Policy runs scripts only from the application’s static
  paths and by a per-response nonce, takes stylesheets only from those paths, and keeps
  images and requests on this origin, so there is nowhere to report to.
  Nothing may frame the page.
- `/raw` is an opaque-origin sandbox, and under the untrusted profile it runs no script
  and serves no file as code.
  A request from that origin is refused by the same-origin check on `/api`, and a page
  it fetches from another origin is unreadable to it.

[SECURITY.md](../../../SECURITY.md#content-trust-model) describes each of these, and
`tests/test_serve_pin.py` holds them against a README that tries each way.

One known limit: the GitHub reducer lowercases the owner and repository so that every
spelling of a URL shares one mirror, so a GitHub repository is named in lowercase
(`hello-world` for `octocat/Hello-World`).

## Cache and Configuration Directories

**Status: implemented for v0.12; release validation tracked by the storage epic.**

Metabrowser follows uv and fdu: macOS and Linux use the same XDG defaults.
Cache and configuration have independent roots and lifecycles.

| Purpose | Resolution order | Default |
| --- | --- | --- |
| Disposable repository cache | `--cache-dir`, `METABROWSER_CACHE_DIR`, `$XDG_CACHE_HOME/metabrowser`, default | `~/.cache/metabrowser` |
| User configuration | `--config-dir`, `METABROWSER_CONFIG_DIR`, `$XDG_CONFIG_HOME/metabrowser`, default | `~/.config/metabrowser` |

Application overrides name the exact directory; XDG variables name a base directory.
Environment overrides must be nonempty absolute paths without `..` components.
Relative CLI paths are anchored to the working directory.
Resolution does not create directories.
Plain local browsing does not initialize storage.

The cache root directly contains `CACHEDIR.TAG`, `layout.yml`, `locks/`, `staging/`,
`sources/`, and `repository-stores/`; there is no additional `cache/` directory.
Every cache record is reconstructible from its source.
Clearing a cache loses offline availability and fetched metadata, but must not erase
configuration. Configuration lives in `config.yml` under the configuration root.
It is initialized once by atomic create-only publication.
Existing configuration, including comments and unknown settings, is not rewritten by
cache creation or cache-layout migration.
Cache and config format versions are independent.

The roots must not overlap, including through symlinked ancestors, so cache deletion
cannot remove configuration.
Both roots retain owner-only permissions and the verified-ancestor, no-follow,
bounded-read, and atomic-publication checks.
Selecting a new location does not relax those checks.
A cache location must support the lock and rename operations verified by the runtime
probe.

This is an intentional v0.12 break: `METABROWSER_HOME` and `~/.metabrowser` are no
longer consulted. There is no alias, automatic migration, or fallback.
Existing files are left untouched.
A future durable data feature must choose a data directory explicitly rather than place
irreplaceable state in the cache.

The implementation is in `home.py`, `cache/paths.py`, and `cache/layout.py`.
`tests/test_cache_layout.py` checks resolution, isolation, initialization, and format
boundaries; the cache-route and CLI golden suites check observable behavior.
See [uv storage](https://docs.astral.sh/uv/reference/storage/) for the convention.

## Shared Repository Store

One logical repository store owns one worktree-free Git database for read-only views of
its origin. It is a bare repository created with an empty template and configuration
written only by Metabrowser, with automatic maintenance and `gc` off.
Fresh acquisition without an admitted lender fetches the objects reachable from the
origin’s branches and tags into a full store.
An admitted checkout can instead lend objects to an [overlay store](#overlay-stores).
A healthy published store keeps its mode and is reused.
These invariants hold for every store:

- there is no shared index or checked-out branch;
- no view operation runs `checkout`, `switch`, `reset`, or `worktree add`;
- its refs are the origin’s branches under `refs/remotes/origin/`, its tags, and the
  `refs/pull/<n>/head` of each pull request opened from it; Metabrowser writes no ref of
  its own;
- a full store owns the objects fetched during acquisition and does not depend on
  alternates into a user-owned checkout or on the origin for those objects; an overlay
  store’s objects are its own or a named checkout’s ([Overlay stores](#overlay-stores));
- tree enumeration and blob reads are bounded and cancellation-aware; and
- Metabrowser does not remove objects: no operation runs `gc`, `prune`, or `repack`, so
  readers need no object-retention lock or ref in a full store.
  An overlay’s borrowed objects can disappear when its lender changes; the overlay
  lifecycle handles that loss.

The repository library assigns a stable internal `RepositoryStoreId`. A conservative,
credential-free Git source identity may create the store before provider resolution.
Later provider binding adds a stable `RepositoryRef` alias.
HTTPS, SSH, provider web URLs, and multiple local remotes may then converge on the same
store without changing their own source records.
Conflicting identities fail closed; they are never merged from owner/name text alone.

A source alias is a generation-checked indirection, not part of a store transaction.
Initial acquisition holds the source-alias lock and the store lock from the store’s
rename into place through the alias commit, and the alias is the sole visibility commit.
A crash between the two renames leaves a completed store no alias names; it is never a
visible half-entry, and the next acquisition of the same source reuses it.
Nothing deletes a published store automatically.
Merging stores by provider identity is deferred by the thin-mirror plan.

### Overlay stores

A store has one of two modes, and every reader is the same for both: the served pin, the
batch readers, `pull_refs.py`, `update.py`, the freshness window, the fetch lock, and
the pull-request records.
`/api/cache/stores` reports the `mode`.

| Mode | Objects | On fresh acquisition |
| --- | --- | --- |
| `full` | Every object, fetched from the origin | No checkout is named, or borrowing is refused |
| `overlay` | `objects/info/alternates` names a checkout’s objects directory, and the store holds what that lacks | The reader named a checkout with `--checkout` |

The design and its experiments are in
[the plan](../specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md).
`cache/lender.py` reads the checkout, and `cache/acquire.py` fills the store:

1. **Only a checkout named now or previously lends.** A healthy published store is
   reused first, including an overlay with its remembered lender.
   On a cache miss without a selected lender, acquisition creates a full store.
   The working directory never grants borrowing permission, because any directory a
   reader stands in can be made to pass for a checkout of any repository, and Git does
   not verify an object’s hash on read.
   If that directory is a matching checkout, the fresh acquisition prints the flag that
   would have selected it.
2. **The checks come first, with no Git in the checkout.** `.git`, `commondir`,
   `config`, and every ref are read as bounded regular files.
   A remote whose identity is the source’s, through the provider’s grammar, is required,
   or the command refuses.
   A partial clone, a lender with its own alternates, unreadable objects, or another
   object format falls to a full clone with the reason printed.
3. **The store’s refs are only what the origin sent.** Nothing is seeded.
   The acquisition fetch is the mirror’s own, with each tip of the lender’s
   `refs/remotes/<remote>/` that the store reads as a commit as a `--negotiation-tip`,
   so the origin sends only what the lender lacks.
   Those tips are recomputed before every fetch, since a tip the lender has lost makes
   Git refuse.
4. **Two more configuration keys.** `core.commitGraph=false`, because the store would
   otherwise read the lender’s possibly stale commit-graph, and
   `core.alternateRefsCommand=true`, or Git runs `for-each-ref` inside the lender on
   each fetch.
5. **The boundary is live, until the store must write it.** `shallow` is a symbolic link
   to the lender’s, so the store’s history stops where the checkout’s does and follows
   it when it deepens; where the checkout is not shallow the link dangles and Git treats
   the store as not shallow.
   Git locks the *target* of a symbolic link when it writes `shallow`, so a
   `fetch --deepen` with the link in place replaces the lender’s file.
   `own_boundary` replaces the link by a copy, or removes a dangling one, under the
   fetch lock before any command that writes the boundary.
6. **A dangling ref is swept.** One ref whose object the lender has collected wedges a
   fetch that neither brings it nor prunes it: a pull request’s fetch on any such ref,
   and a refresh on a `refs/pull/<n>/head`, which its refspecs do not name.
   So before each fetch into an overlay, under the fetch lock, `for-each-ref` and one
   `cat-file --batch-check` find such refs and `update-ref` deletes them.
   A ref the origin still has comes back with the fetch.
   Git answers `missing` alike for an object the lender collected and one it holds and
   cannot lend now, so a ref is deleted only when the lender shows its object gone: no
   loose file of it, whatever its mode, and every file of its pack directory readable
   (`collection_doubt`). Otherwise nothing is deleted and the fetch is refused as
   `lender_missing`, which also covers a lender whose refs no file holds, as reftable
   keeps them, so that the probe of its tips through the store has nothing to read.
7. **The record and the file agree.** `store.yml`’s optional `lender` names the objects
   directory, the checkout, and the remote.
   Absent means `full`. A record and an alternates file that disagree is `damaged`,
   checked at open and reported by the cache routes.
8. **A lender that has gone is refused at open.** One `stat` of the borrowed directory:
   `lender_missing`, with the recorded path and the repair, `--checkout <new path>`,
   which runs the same checks.
   A refresh in a running server reports `lender_missing` as its outcome and fetches
   nothing, and a read of a borrowed object answers `object_unavailable`. Cache routes
   read records and no object, so they still answer.

Complete object reads verify the Git object ID against the header and bytes, using the
store’s SHA-1 or SHA-256 format.
A mismatch is `object_corrupt`. Windowed reads hash discarded prefixes and tails only
when the existing drain bound consumes the complete object.
A larger partial window stays useful and makes no claim of whole-object authentication;
verification does not extend its read bound.

A borrowed comparison verifies only the blobs of the files being hydrated, within the
existing per-run byte budget.
It does not hash an entire manifest or walk history.
Detected corruption prevents a response body from being cached and invalidates any
in-memory manifest for that comparison.

`git/object_failures.py` keeps at most eight observed object IDs for each of sixteen
store/commit selections, for ten minutes.
It retains no object bytes or Git diagnostics.
`cache/object_recovery.py` handles an explicit recovery: check the displayed immutable
commits and those observed IDs, fetch missing IDs under the existing fetch lock and
sweep rules, then authenticate them before clearing the observations.
The recovery has one sixty-second deadline, including lock waits.
Before declaring success it advances the store reader pool’s generation and reaps idle
actors, so no later request reads an unlinked obsolete pack.
Actors already leased to a request finish their transaction and are recycled on release;
repair does not interrupt that request.
Cancellation during recycling preserves the stale queue slot for the next reader to
recycle. An ordinary commit fetch can succeed while leaving a descendant blob absent;
exact-ID fetching repairs that object without changing a ref or writing the checkout.
A corrupt lender that Git still claims to have remains a typed refusal, and an origin
that no longer serves a displayed object is `commits_unavailable`.

Measured on macOS with nine alternating pairs, complete-read hashing added 0.021 ms for
3.9 KiB, 0.029 ms for 64 KB, and 4.586 ms for 8 MiB. The 32 MiB partial-window path
calls no hash; its timing pairs were too noisy to establish a difference.

### Cache record contracts

The records Metabrowser writes into the application home are enforced SoftSchema
contracts. `cache/contracts.py` binds each contract ID to one Pydantic model in
`cache/records.py` and one compiled Draft 2020-12 schema packaged under
`data/cache-format/`, and `plugin_loader/artifact_contracts.py` checks each declaration
and validates every record on read and on write.
The registry is internal: nothing outside this package declares a contract, and there is
no entry-point group or public type for one.
A cache file names its contract, envelope, and status but never a schema path: the
caller chooses the contract from the file’s place in the layout, so cached data cannot
select the schema that validates it.
`config.yml` is user-owned and validated permissively, so it is not in this table;
`check_packaged_schemas` compiles it with the others.

The table registers the installed contracts.
`devtools/check_artifact_contracts.py` compares it with the cache’s declarations and
runs each contract’s schema, semantic validator, positive and negative conformance
corpus, and deterministic round trip.
The distribution check runs the same inventory against isolated wheel and source
distribution installs, so a declaration or evidence file that exists only in the source
tree cannot pass.

| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus |
| --- | --- | --- | --- | --- | --- |
| `metabrowser.cache:CacheLayout/v1` | `pure-yaml` | `layout` | `repository-cache` | `repository-cache` | `cache-records-conformance[layout]` |
| `metabrowser.cache:RepositorySource/v1` | `pure-yaml` | `source` | `repository-cache` | `repository-cache` | `cache-records-conformance[source,scp_source]` |
| `metabrowser.cache:RepositorySourceState/v1` | `pure-yaml` | `state` | `repository-cache` | `repository-cache` | `cache-records-conformance[source_state]` |
| `metabrowser.cache:RepositoryStore/v1` | `pure-yaml` | `store` | `repository-cache` | `repository-cache` | `cache-records-conformance[store]` |
| `metabrowser.cache:RepositoryStoreAlias/v1` | `pure-yaml` | `alias` | `repository-cache` | `repository-cache` | `cache-records-conformance[store_alias]` |
| `metabrowser.cache:RepositoryStoreState/v1` | `pure-yaml` | `state` | `repository-cache` | `repository-cache` | `cache-records-conformance[store_state,empty_store_state]` |

### Read path and performance

The revision source resolves a root tree once and caches its immutable directory index
by tree object ID. Blob access uses a bounded pool of long-lived batch Git readers
rather than spawning one process per file: at most four per store per process, created
on demand.
Every read runs with `-c mailmap.blob=` and `-c mailmap.file=`, because a bare
store’s default mailmap is `HEAD:.mailmap`, and with `GIT_NO_LAZY_FETCH=1` as defense in
depth: a store has no promisor remote, and the spawn seam refuses a store read whose
policy would leave lazy fetch on.
Blob sizes come from the batch readers’ `info` answers rather than `ls-tree -l`. Git can
report a failed read on stderr and still exit 0, so stderr from a store read degrades
the result rather than passing as success.
Diff, commit-detail, and comparison reads run Git directly, because a store has or
borrows every blob they read.
Those commands pass neither `--no-ext-diff` nor `--no-textconv`, so they honor the diff
drivers of the repository’s own configuration.
A store’s configuration has none, and a borrowed checkout’s is not read, which is one
reason a checkout’s objects are read only through a store.
A served checkout’s Commits tab does honor its own, as `git diff` there would.
Diff, history, commit detail, and tree reads receive a trusted Git command target that
may name either a worktree plus Git directory or the shared worktree-free store.

`GitCommandTarget` is a closed core type with `AttachedWorktreeTarget` and
`RepositoryStoreTarget` variants.
Core-only constructors validate the worktree and Git directory and expose allowed
command capabilities; callers cannot inject Git environment or command prefixes.
Repository discovery, history, refs, commit detail, diff adapters, and comparison
builders accept this target explicitly.
An immutable subject starts history and detail from its pinned full object ID rather
than ambient `HEAD`; refs are observations, and every diff receives the same target plus
exact OIDs.

### Fetch and credentials

`file://` and `https://` are fetched: acquisition, and refresh of a published store.
A refresh is `ls-remote --symref` of the origin’s URL for the default branch, then
`fetch --prune --atomic --no-write-fetch-head` of every branch and tag from that URL, so
every ref moves together or none does and a branch or tag deleted upstream leaves the
mirror while its commits stay.
`cache/origin.py` builds both commands for acquisition and refresh alike: a protocol
allowlist of `file` and `https`, a low-speed stall bound measured beside its constant,
and whatever a provider adds for that URL. The GitHub provider adds `gh` as the only
credential helper, scoped to `https://github.com` after every configured helper is
cleared, so Git asks it only after a server challenge and public repositories stay
anonymous. Acquisition and refresh Git run with `HOME=/dev/null`, because curl reads
`$HOME/.netrc` and Git cannot turn that off; `gh` alone is given the real home in its
helper command, and the `GH_*` variables that would redirect or log it are cleared
there. The first command against an https origin has its own deadline, because curl’s
low-speed bound does not cover a TLS handshake that never completes; the fetch has none,
so a clone that is making progress is stopped only at the acquisition deadline.
Failures read as typed states (`not_found_or_private`, `network_unreachable`,
`connection_interrupted`, `tls_failed`, `timed_out`, `server_error`, `rate_limited`,
`proxy_auth_required`, `too_large`) and never as Git’s own text; a refresh reports the
same names as its outcome.
Ref names resolve by exact, case-sensitive match against the names the store holds.
On a case-insensitive filesystem two origin refs that differ only in case are one loose
file, so acquisition refuses such an origin as `ref_case_collision` rather than publish
a ref that names the other’s commit, and a refresh reports the same outcome.
A refresh cannot rely on Git failing: when the origin gains `SAME` beside an unchanged
`same`, the atomic fetch writes `SAME` into `same`’s file and succeeds.
So on such a filesystem a refresh lists the store’s refs before it fetches, and
afterwards checks what a fold breaks (`cache/resolve.py`: `folded_refs`): a ref the
fetch neither wrote nor pruned must still name its old object, and every ref it wrote
must be held at that object under a name the filesystem folds to the same one.
Names are compared as the filesystem does, because it respells without moving anything:
`Feature/x` written into an existing `feature/` directory lists as `feature/x`, and Git
lists a decomposed name precomposed.
The check and any restore run to the end even when the refresh is cancelled, and a
cancelled refresh on such a filesystem puts the refs back as they were before it.
A restore is two `update-ref --stdin` transactions, retried a ref at a time when one is
refused; refs it still cannot put back are logged by name, and the refresh reports
`ref_case_collision` rather than success, without moving the recorded tip.
If it does not, every ref is put back as it was, objects being kept, and the outcome is
`ref_case_collision` with neither the recorded fetch time nor the default branch’s
commit moved. Every fetch runs in the isolated Git environment of `git/process.py`, the
only Git subprocess boundary: no inherited `GIT_*` variable, no system or global
configuration, terminal prompting disabled, and hooks off.
Git runs in its own process group, so a timeout, Ctrl-C, a terminal hangup, or `SIGTERM`
kills the helpers it forks as well, including a cancellation that arrives while Git is
still starting. Being outside the terminal’s foreground group, a serving refresh’s Git
does not hear a hangup itself, so the server takes a hangup as it takes Ctrl-C: it kills
the live Git process groups and exits.
Acquisition never inherits an attached checkout’s remote or credential helper.

### Pull-request records

A GitHub pull request is two things kept apart: its commits, which Git fetches into the
store, and its data, which `gh api` reads into one JSON record under its source.
`cache/pull_refs.py` fetches `+refs/pull/<n>/head:refs/pull/<n>/head`, the one ref a
store holds beyond the origin’s branches and tags, from the source’s URL with
`origin_git_args` under the acquisition policy and Git floor; a fork’s commits arrive
through it.
Every such fetch holds the store’s fetch side lock, as a mirror refresh does,
removes what a killed fetch left first, and hands the lock’s descriptor to Git; a pull
request’s refresh that finds another refresh holding it tries again for up to a minute,
then reports `refreshing_elsewhere`. On a case-insensitive filesystem the base branch is
fetched, and compared from, only when the store lists it under exactly that name, since
one kept under another spelling shares that ref’s file; otherwise the comparison starts
from `base.sha`. What it writes gets the mirror update’s case-fold check, and a fold
puts every branch and tag back.
An open pull request’s base branch is fetched in the same command into the
`refs/remotes/origin/<base>` the mirror update writes, so its merge base is taken
against the base branch as it is now.
A closed or merged pull request compares from the API’s `base.sha`, fetched by ID when
no mirrored ref reaches it.
The fetched head must be the head the API reported; one full re-read covers a push
between the two, and a second mismatch is `head_mismatch`.

The record lives at `sources/<slug>/pulls/<n>.json`
(`cache/paths.py: source_pull_record`), written by the home’s private atomic file write
and read with a size bound.
The source directory is enumerated by nothing, so the layout, probe, sweep, and
`/api/cache/*` projections leave it alone.
`builtin_plugins/github/pull_record.py` holds its Pydantic models and every bound, with
the measurements beside the constants; a record whose `schema_version` differs is
refetched, not migrated.
PR refresh prepares the comparison manifest before publishing the record.
`builtin_plugins/github/pull_manifest.py` owns a disposable bank at
`repository-stores/<store-key>/github-pull-manifests/<slot>.json`: sixteen direct-mapped
slots, each admitted only within the existing 16 MiB PR-record read bound.
A slot holds a versioned File Diff Format document with no patches, its digest, and the
full build, store-token, endpoint, and base-policy identity.
A collision evicts a slot and causes a later miss; it cannot return another comparison.
The PR comparison route resolves the requested commits before adopting a validated
manifest, and a missing, corrupt, or mismatched entry is recomputed once through the
existing shared comparison-cache task and replaced atomically.
Persistence failure leaves the PR record and computed answer usable.
Persisted manifests are adopted only when their private bank currently permits writes,
including effective access and read-only mount checks; a read-only bank still serves
recomputed comparisons.
Detected corruption first attempts to invalidate the exact slot atomically, then
advances that slot’s epoch beside the bank.
The epoch makes old data miss even if the slot could not be written and its permissions
are restored before a restart.
A manifest captures that epoch before computation, so an older in-flight write cannot
relabel itself as current.
A missing epoch starts a new one; a malformed or unreadable epoch disables persistence.
There are at most sixteen bounded epoch records, one per slot, with no index, scan, or
lock; invalidating one slot leaves the other disk hits intact.
If the epoch cannot be written, the response requires clearing the affected repository
cache before retrying; no process can retain new corruption knowledge across a restart
when every persistence attempt fails.
`GET /api/plugin/github/pull-comparison` reads only the selected PR’s published store
and never fetches. Its initial answer hydrates eight ready files.
The shared diff service retains its fifty-file default for other callers; encoded bodies
and entity tags include the initial-file policy, while the manifest key is shared.

It names its reader, always `gh:<login>`, because `gh api` refuses requests while signed
out, and the account is read before and after the API reads so a record read across an
account switch is discarded.
Requests carry the previous record’s ETags when the same reader wrote it, and a `304`
reuses that part. A page larger than `gh`’s output cap is asked for again in smaller
pages, down to one item; an item still too large, or one that cannot be read, is left
out and its list marked incomplete, and each list has a request cap as well as an item
cap. Every text field is budgeted on its JSON-escaped size, so a written record always
fits the read bound.
Check runs and statuses GitHub refuses, and a comparison whose base cannot be fetched,
are named in the record’s `unavailable` rather than failing it.
`GET /api/plugin/github/pull?number=<n>` reads the record for any pull request and never
fetches, parsing it again only when the file changed; the one-shot CLI fetches a missing
record once for the pull request its URL names, and `--no-serve` refreshes it.
When a pull request cannot be opened, the CLI answers from a cached record, or falls
back to the default branch or the commit URL’s commit, and says why.
The route’s `pin` is the served commit, and the record’s head names the head it was read
at; they differ when the pull request was opened from a branch or another pull request,
for a commit URL inside the pull request, and after a refresh finds a newer head, which
the pull-request page offers rather than switching to.
A server serves any pull request of a GitHub mirror: the CLI hands it the provider’s
`ServedPulls` (`builtin_plugins/github/served_pull.py`), a `PullRequestSet` of the
mirror session, which gives a `ServedPull`, a `CompanionRefresh`, for a number.
It keeps the state of `MAX_KEPT_PULLS` in memory, since the numbers are request text,
and reads the rest from disk.
A refresh is a coordinator job keyed by store key and number, so requests join it, it
counts against the limit of two, and shutdown cancels it; `MAX_PULL_JOBS` bounds how
many may be queued or running.
The session attends to one pull request: the one the URL named, replaced whenever a pin
switch serves another’s head.
Its record’s age counts toward status `stale`, and the source’s refresh starts whichever
of the two jobs is stale, so serve mode’s refresh of a stale source at startup and the
page’s refresh when a stale page becomes visible keep it fresh without fetching a fresh
mirror for it (a one-shot command refreshes the mirror it asked for).
A pull request with no record is fetched only by a reader’s own request, and one with a
record refreshes when its page asks and it is due.
A pin the mirror lacks fetches the mirror, and a commit pin also refreshes the attended
pull request, whose `refs/pull/<n>/head` may bring it; a branch or tag pin never runs
`gh`. Within one server these jobs take turns before the store’s fetch lock
(`StoreTurn`), so none finds another holding it and reports a refresh running elsewhere.
The mirror’s fetch and the attended pull request’s go first, since a page of code waits
on them, and a job takes its network slot only once its turn has come, so a list’s
refresh does not wait behind a queue of pull requests.
A pin by commit ID that is the tip of a fetched pull-request head is served under that
head and attends to it, whichever page asked: a commit page does this as View file does.
How each refresh ended is kept beside the record in `pulls/<n>.refresh.json`, so the
route and a later command report it, and a failed one is tried again after a window, not
on every poll or by the next command, and after `rate_limited` not before `reset_at`.
`POST /api/plugin/github/pull-refresh` with `{"number": <n>}` starts or joins the job
and returns `202` at once, naming `/api/plugin/github/pull?number=<n>` as its
`status_route`; a one-shot `--api` waits for the job, prints that route, and exits 1
unless the refresh succeeded; one that found the store busy did not refresh the record.
After the job, the session reads the pinned ref’s tip again, so a newer head behind
`refs/pull/<n>/head` is offered as `latest`, and `resolve_pin` accepts that ref.
One-shot modes fetch only a pull request with no usable record, or one whose commit URL
names a commit the mirror lacks, which only its `refs/pull/<n>/head` can bring, before
serving. `gh` runs as the leader of its own process group, registered with Git’s, so a
Ctrl-C or hangup that cannot unwind kills it too.

The pull-request page (`builtin_plugins/github/pull-page.js`) is the view the GitHub
plugin registers for the `pull-request` kind, which the shell mounts at `/pull/<n>` and
`/pull/<n>/files`; a served pull-request URL opens there.
It reads the pull route only, polling it with an entity tag while visible, and renders
each text as Markdown through
`GET /api/plugin/github/pull-markdown?number=<n>&part=<part>`, which renders one text of
the cached record through KPress’s sanitized mode and then reduces it to an allowlist of
plain markup, on the server and again in the page, so nothing in it loads, restyles the
page, reaches the application’s handlers, or names an element.
The page sets the result in a KPress article of its own making, under KPress’s
stylesheets, so a text reads as the same Markdown in a file does.
Files changed is the diff plugin’s view over the record’s comparison, passed as two
endpoints with `base_policy=merge_base`.

**A merge base on a shallow store is believed only when it is certain**
(`git/shallow.py`). `merge-base` on a cut graph can name a common ancestor that is not
the best one, with no error.
Its answer *M* is certain when `rev-list <base> <head> ^<M>` names no commit in the
store’s `shallow` file, or when *M* is one of the tips; the module holds the proof,
which needs only that the cut graph is a subgraph, so a crafted boundary can make an
answer uncertain and never certain and wrong.
An empty answer on a shallow store is uncertain, and not `no_merge_base`. When
uncertain, the refresh job writes the record with
`unavailable.comparison: base_uncertain` and no comparison, then fetches `--deepen` of
the base and the head into the store in up to five growing rounds, within the
acquisition deadline, and writes the record again if that settles it.
Offline, or still uncertain, `base_uncertain` stands, and the page shows no diff.
The comparison route refuses the same way when asked for two tips directly.
The boundary is read before and after every Git command the check runs, on every return,
since the store’s `shallow` can be a link to a checkout that deepens or becomes shallow
meanwhile: an answer computed on another boundary than the one read is uncertain.
`no_merge_base` is only Git’s own answer that the two share no history; a `merge-base`
that failed could not read a commit on the walk, on an overlay an ancestor the checkout
has collected, and that is `commits_unavailable`.

A commit at the boundary is one more cut: Git grafts it into a root, so its own diff
would be taken against the empty tree and show a whole tree as added.
`git/shallow.py` reads the commit’s parents from the object itself, which the graft
never touches, so `/api/plugin/diff/comparison?revision=` answers the typed
`parent_unavailable` for it and `/api/git/commit/<id>` reports its `stats` as unknown,
on a store and a served shallow checkout alike; a real root commit is unchanged.

### Lightweight pull-request cores

Preparation stores each validated header and description in
`sources/<slug>/pulls/<n>.core.json`, separately from the full record.
`pull_core_cache.py` uses the existing private-file helpers, record read budget, and
source-alias lock. The entry names the source, repository ID, reader, catalog epoch,
summary fingerprint, observed time, and validated core.
Publication rechecks identity and the exact catalog member under the source lock after
the provider read.

The fingerprint determines whether background preparation needs to fetch again.
An ordinary catalog refresh retains its epoch, so unchanged entries remain reusable.
A changed summary permits immediate display of its older validated core while another
preparation fetches the update.
Replacing the account, repository identity, or catalog epoch refuses the old entry.
An observed account change also revokes old-reader lookahead in the current server.
A newly authenticated catalog advances the server’s remembered reader and hold scope; an
ordinary revision in the same catalog identity does not.

The freshness window bounds retry frequency, not the lifetime of useful metadata.
A core remains readable after a minute, releasing its preparation window, scrolling
away, or restarting the server.
A complete cached record takes precedence.
GET reads local state only; it starts no provider, discussion, diff, or Git work.
Disk validation runs off the event loop, followed by a memory-only ownership and reader
check on the loop immediately before the response is constructed.

A preparation request names at most one transport batch.
Only a `202 started` or `202 joined` response admits the request as a server-window
owner. A `200 ready` or `200 partial` response reports coverage and can leave a previous
window owned. The client clears its owner handle and releases that previous exact token
before advancing coverage or admitting another cohort.
A ready receipt lists `ready_numbers` backed by validated cores and `skipped_numbers`
with readable full records.
An unreadable or schema-mismatched record supplies no coverage; its separate validated
core can still serve the description.
The two lists cover a completed batch without one status request per PR. A settled
partial batch instead returns `partial`, these two lists, `retry_numbers`, and
`retry_at`. The three disjoint lists account for every requested member.
An unavailable PR retains its attempt lease while valid siblings and later cohorts
proceed; callers revisit unfinished members after that deadline.
Settled partial owners retire, so a later retry can prepare their missing members.
A failed owner batch returns `failed`; subsequent batches return `held` with the same
outcome, message, and reset time until another attempt is eligible.
`cores.refresh.json` persists provider and malformed-response holds under the same
catalog identity. A successful batch records success so an expired refusal cannot return
after restart; an older writer cannot erase a newer outcome.
Known rate resets take precedence; a missing reset uses the existing minimum hold and
backoff. Source failures leave useful cores intact and cannot start one failed provider
process for every queued row.

Successful durable publications release transient cooldown capacity.
Neither transport batch size nor that bounded in-memory bookkeeping limits total
coverage. Foreground selection still cancels and drains an active preparation job before
starting its selected read.
The focused core sessions in `tests/test_github_pulls.py` cover multiple batches, stale
display, changed identity, offline restart, and failure holds;
`cli-github-pulls-refresh.txt` demonstrates the same persisted read and cache-only
receipt through the CLI.

### Lists of pull requests

The GitHub plugin owns one disposable SQLite metadata catalog at
`sources/<slug>/pulls/catalog.sqlite3` (`pull_catalog.py`). Rows are keyed by PR number;
a `(state, number)` index serves Open and Closed windows, with merged rows classified as
closed. The checkpoint holds repository identity, account, exact provider counts, cached
counts, scan cursors, freshness, and content generations.
Listing takes only `ListedRepository` (home, slug, owner, repository), never a Git
store.

`refresh_pull_list` requests fixed GraphQL pages of at most 100 lightweight rows.
Descriptions, comments, reviews, checks, patches, and repository objects are absent.
The worker prioritizes the requested filter’s newest display prefix, then backfills all
PRs in descending creation order.
It resumes a committed cursor after cancellation or restart.
A changed account or repository identity atomically replaces the catalog; a rejected
cursor restarts that scan once without discarding already cached rows.
GraphQL errors, including HTTP 200 with partial data, never advance a checkpoint.

A catalog job checks the active GitHub account once before choosing its checkpoint.
Every page query returns `viewer.login`; it must match that job’s reader before any rows
or cursor are published.
Ownership follows the account that returned the data: changing local account settings
after a response does not relabel or discard that response.
A later page from another account is refused, leaving the last committed checkpoint and
its reader intact. A new job under that account replaces the catalog atomically.
`gh auth status` performs an HTTP authentication check, so the catalog does not repeat
it after each page.
Cached reads retain their recorded reader and do not check the active
account. Pull-request detail and file-list refreshes keep their own account checks.

A refresh scans descending `UPDATED_AT` pages through the inclusive previous watermark.
It captures the next watermark at scan start and advances freshness only when that scan
finishes.
Backfill pages never make old metadata fresh, and a row’s `updated_at` prevents
older backfill from overwriting a newer update.
Provider counts are dated observations, not counts derived from cached rows; the
all/open/closed fields need not be an atomic snapshot of a changing repository.
Rows absent from an incomplete scan are not inferred deleted.
A deleted or newly inaccessible historical PR may remain in the disposable catalog until
it is rebuilt.

Each page commits its rows, counts, and cursor in one short transaction under the
existing source-alias lock.
A checkpoint revision rejects a publisher superseded by another process.
Cached counts change from each row’s old and new state, avoiding a whole-catalog count
or rewrite per page.
Network and Git work never run under the lock.
Cancellation abandons a waiting publisher before it can write.
One job per source holds a coordinator network slot for one page at a time and yields
between pages, so opening an individual PR can proceed during a long backfill.

GET uses bounded indexed queries in a read-only transaction.
Private-path admission checks the database and existing SQLite sidecars, and rejects
WAL-format databases before SQLite opens them.
The writer uses rollback journals.
Readers and writers admit only the exact two tables and required index; extra triggers,
views, or altered schema are refused before a checkpoint or row is used.
The database is initialized in memory and published atomically, so an interrupted
initialization cannot expose a half-built schema.
Empty initialization remnants can be rebuilt by an explicit write; corrupt or unknown
schemas receive a typed cache-write refusal requiring the affected repository cache to
be cleared. Reads create no database, journal, source, or store and never widen
permissions. SQLite value limits and a read instruction budget bound malformed-cache
work.

The last outcome remains in `list-all.refresh.json`. A failed refresh preserves the last
committed page; a stamp that cannot be written is retained in process memory.
Automatic retries wait a freshness window, and a known rate-limit reset holds every
request. The server’s `served_repository` selects its managed store or a served
checkout’s validated GitHub origin; neither yields a source for an unrelated folder.

### Optional native stack metadata

The GitHub plugin stores one bounded disposable `sources/<slug>/pulls/stacks.json`
snapshot independently of the catalog and PR records.
The snapshot records its source, reader, fetch time, completion flag, native stack
numbers and ordered PR membership, plus each page’s ETag and continuation.
Cached reads run no processes and create nothing.

A separate coordinator job probes `gh stack --version` from an isolated directory, then
reads repository-wide GitHub REST stack pages.
It never runs `gh stack view`, checkout, sync, or tracking commands.
Unlike the catalog’s GraphQL response, a REST page has no embedded reader; this job
checks the active account before and after its pages.
Changed accounts, foreign repository URLs and malformed pages cannot replace a known
snapshot. A source-lock revision check rejects superseded publishers; cancellation
abandons a waiting publisher.
Network work stays outside the publication lock and yields the shared slot between
pages. Each request checks optional and catalog rate holds after acquiring its slot;
optional outcomes never overwrite core refresh stamps or records.

An unchanged page’s `304` retains its cached continuation even when `Link` is absent.
A refresh publishes only the pages it actually revisited, so a shorter result cannot
retain an old tail. Multiple distinct native stacks may name the same PR; each stack
retains its own complete bottom-to-top member order.
The bounds are 10 pages of 100 stacks, 8 MiB of normalized cache data, 1,000 members per
stack, and 10,000 memberships per snapshot.
A whole page that would exceed the snapshot budget is omitted and `complete` is false;
an oversized individual stack is refused.
Missing membership in a partial or unavailable result never means the PR is unstacked.

Successful and failed attempts have a five-minute window, with remaining freshness in
the envelope. Explicit retry reprobes optional capability, but a known rate reset still
holds it. Failure retains a preceding snapshot; a refused cache write records bounded
process-local backoff.
`403` and `404` are neutral unavailability, not proof that the repository has no stacks.
Native stack numbers are labels, not PR numbers; the API URL is not a browser stack
link. See the [route contract](arch-views-models-routes.md#data-routes).

### Pull requests beside a checkout

A folder’s pull routes resolve its checkout’s `origin` to the GitHub plugin’s canonical
repository identity.
Metadata reads create nothing, and metadata refreshes can publish an unattached source.
A healthy store already attached to that source is reused without acquisition or a cache
timestamp write.

Selecting **Changes** starts one comparison attempt after the metadata settles if its
record lacks a store.
The browser sends `retry: true` and `comparison: true` to the PR refresh route.
The server acquires the store with the checkout as its lender.
The pull record then uses the same store API and comparison service as a managed URL.
The served folder root and Commits tab stay unchanged; no Git process runs in the
checkout, and the checkout is never written.
A served subdirectory resolves to its enclosing checkout before acquisition.
Lender paths stay inside private cache metadata.

A comparison request that joins an active metadata job is retained until that job can
acquire the store. Jobs take their turn at the store before consuming a network slot.
An acquisition failure preserves the last pull record and reports a typed refresh
outcome. `GET` routes never acquire or fetch.

**Changes** offers Refresh for a displayed comparison even while its record is fresh.
The reader’s action sends `retry: true` and `recovery: {base, head}` for the comparison
still displayed. Automatic metadata refresh remains stale-only.
Metadata updates do not replace displayed changes: a successful repair remounts that
same comparison once and restores its scroll position; a failed or waiting job leaves it
in place. The existing newer-changes action remains the way to select a newer head.
The browser offers a retry after comparison preparation fails.

The server validates complete object IDs and a pair issued by that PR in this session
before permitting repair.
Each held PR retains eight issued pairs and protects its last displayed pair from
metadata eviction. An explicit retry joining a running job is queued, even if that job
fails; equal queued selections coalesce.
Number-only explicit refresh continues to repair the current cached comparison.
Old full-endpoint GET links remain readable after a restart, but an old pair that this
session cannot associate with the PR cannot authorize network repair.
No persistent comparison history is added.

Only IDs observed missing while reading that comparison and its two endpoints are
checked and, when absent, fetched exactly.
A complete recovered object must match its ID before its failure is cleared.
Detection of corrupt bytes invalidates in-memory answers and the persisted manifest;
failure to discard that metadata is reported.
A corrupt lender is refused without modifying its objects.
Large partial previews retain their existing read bounds and do not claim a whole-object
authentication.

If a cached managed source loses its pinned root tree before startup, opening it reports
a path-free pin-open error without a traceback or automatic clone.
Live Files Refresh requires a running source; startup does not start an implicit repair
fetch.

### Changed files of a pull request

A pull request’s changed files are one more file beside its record:
`sources/<slug>/pulls/<n>.files.json`, with `<n>.files.refresh.json` for how its last
refresh ended (`cache/paths.py: source_pull_files`). `PullFileList` in `pull_list.py`
holds the model and its bounds with their measurements, written atomically as a private
JSON file and read with a byte limit.
File-list schema 2 requires a `generation`: one opaque UUID minted after source
admission for the entire logical refresh, shared by its local or GitHub publications.
It stays stable through progressive pages and subsequent reads, including a server
restart. Concurrent refreshes have distinct generations even at the same timestamp.
Older or malformed file-list records are a typed cache miss; a passive read never
rewrites them. An explicit refresh can replace disposable records in an admitted home.
Source admission refuses unknown or future application layouts.
A worker rejected at this boundary attempts no cache write.
Work that passed admission earlier can still publish later; refusal does not drain
concurrent writers or coordinate a live layout upgrade.
A row keeps `path`, `previous_path`, GitHub’s `status`, and the line counts; GitHub’s
embedded patch is dropped before anything is kept.
The path is the row’s identity, a rename’s new path, since the diff view jumps to a file
by its path.

`refresh_pull_files` (`pull_files_refresh.py`) has two sources for one list.
When the record’s comparison names two commits and the server has a store, it lists that
comparison’s manifest with `GitDiffSource` (`--raw` and `--numstat`, no patch) and no
network, as `listed_from: "comparison"` with the `head` it belongs to.
A manifest cut at `MAX_MANIFEST_FILES`, or one Git cannot list, as on a mirror whose
checkout is gone (`lender_missing`) or has collected the head (`commits_unavailable`),
falls through to GitHub’s list, which runs no Git: the account, then
`repos/<owner>/<repo>/pulls/<n>/files`, one page of a hundred at a time up to GitHub’s
3,000 files. The worker checks that the active account still matches the record’s reader
before each progressive-prefix publication and before publishing the complete list.
An observed change stops the job with `account_changed`; previously checked prefixes
remain readable and the envelope marks them stale.
`tests/test_github_pull_files.py` lists a source directory that has no store, with a
`git` first on `PATH` that fails and logs.

GitHub’s list is published after every page that leaves it holding more rows than the
file does, as `complete: false` with the page count GitHub’s `Link` gave, so a reader
sees a first list arrive and a held one never shrinks while it is reread, each page with
its `If-None-Match` and a full last page whole; the whole list is published at the end.
A failure leaves the file as last published, and its stamp says why.
The reader uses generation and repository/account/comparison identity to distinguish a
replacement from an appended page; timestamp precision does not establish identity.

A source-admission failure occurs before a refresh stamp can be written safely.
The worker then keeps `cache_unwritable` in the bounded in-memory outcome cache, exposes
it through the normal envelope, and holds automatic retries without contacting GitHub or
attempting a lock, directory creation, or write in the refused home.
Reading the refresh outcome selects the newest `at` from memory and disk independently
of the strongest unexpired provider `reset_at`. An older, delayed provider hold
therefore keeps its network deadline without hiding a newer `cache_unwritable` outcome
or message. While a provider hold is active, equal-`at` outcomes retain precedence for
the stronger reset deadline; exact ties prefer memory.
With no active hold, equal-`at` outcomes keep the existing memory-first tie rule.
The memory-only outcome can be lost on restart or eviction; it is not a durable cache
repair. After admission, the worker attempts normal stamp publication.
`tests/test_github_checkout.py` covers real refused layouts and unchanged home/config
fingerprints; the file-list and tree session tests cover replacement, append, and read
stability. `tests/test_github_pull_files.py` covers delayed shared holds, newer refusal
outcomes, and expired equal-time holds.

The job runs on the refresh coordinator under `<slug>:pull/<n>/files`, started outside
the network slots. Each `gh` request acquires and releases its own network slot; the
file-list job does not retain a slot between requests.
It takes no turn at the store.
At most `MAX_PULL_JOBS` file lists may be queued or running, since the numbers are
request text; past it a request is refused `too_many`.

### Git path and blob semantics

`GitPath` is an immutable tuple of raw non-NUL byte segments with bytewise equality and
stable byte ordering.
It is never converted to a host `Path`. The wire codec encodes each segment as `g1-`
plus unpadded base64url; envelopes carry a separate replacement-safe display string.
Tree routes, file routes, diff entries, review anchors, and provider URL reductions use
the same identity. Parent and child operations manipulate segments, not slash-joined
native strings. Markdown and wiki destinations on a pin encode authored segments with
that same wire; the known-file catalog indexes the tree node’s display name, not the
`g1-` token. SPA path chrome and copy-path decode those wires to display names;
navigation identities stay wires.
Omitted size, mtime, and directory aggregates leave tally chrome empty rather than
pending.

Tree enumeration uses NUL-framed Git output.
Symlinks are entries whose blob bytes name the link target, and enumeration never
follows them.
File, raw, KPress, and plugin content reads follow an in-tree relative link
one component at a time, as a checkout on disk resolves it, and refuse one that is
absolute, climbs out of the tree, or does not end within `_MAX_GIT_SYMLINK_FOLLOW` hops.
Gitlinks are distinct non-folder entries that carry the referenced commit OID. Git LFS
pointer files remain ordinary blobs; no smudge filter or implicit LFS network request
runs. Focused tests pin that `cat-file` returns the stored pointer bytes even when a
smudge filter is configured.

Each long-lived `cat-file --batch-command` process is owned by one actor and serves one
exclusive request at a time.
It issues `info` before `contents`, rejects a blob whose declared size exceeds the
measured preview or raw limit, and drains the complete frame.
Cancellation, timeout, unexpected framing, or a short body poisons and restarts the
process. Only validated full OIDs enter the line protocol; byte paths are resolved
separately through NUL-framed tree lookup.
A blob the tree names but the store lacks, which only a damaged store can produce, is
reported as `object_unavailable`, and a later present blob still reads on the same batch
actor.

A valid repository subject opens without network access, and every read answers from the
store alone, with the origin reachable or not.
A refresh runs only as a background job a request starts or joins, never inside a read;
a failed one leaves the served revision as it was and reports a typed outcome in
`/api/source/status`. The freshness window and its measurement are beside
`FRESHNESS_WINDOW_S` in `mirror_refresh.py`.

## Shared Provider Mirror

Provider storage is keyed by:

```text
(provider kind, provider instance, stable repository opaque ID,
 authorization-context key, logical target/profile/query)
```

It is not stored under a generic cache entry or local checkout.
A source attachment maps a conservative source identity to a stable `RepositoryRef`;
many source identities and ephemeral local sessions may map to one provider repository.
The attachment contains no absolute local path and is independent of authorization.

The mirror contract is intentionally precise:

> For every enabled resource profile, provider instance, repository, authorization
> context, and query, cached state is a read-only validated observation of the provider
> API. Normalized artifacts are immutable.
> Refresh stages and atomically publishes a new acquisition; it never edits an existing
> artifact. Data outside enabled profiles is explicitly not requested.
> Absence is authoritative only when the profile and retrieval evidence prove it.

This is a mirror of the supported, enabled product slice, not an undocumented copy of
every GitHub response.
Raw provider payloads are not the application model.

The physical artifact pool may deduplicate identical bytes.
Current pointers, validators, reachability, deletion evidence, and refresh decisions
remain isolated by authorization context because two principals can observe different
repository state. Provider APIs may not offer one transaction across all endpoints, so a
locally atomic manifest still records `provider_snapshot`, `best_effort_window`, or
`unknown` remote consistency for the complete resource set.
“Last complete” means every required collection was acquired, not that every endpoint
represented one provider instant.

## Attachments and Activation

Opening an ordinary local Git repository performs no provider network work.
When a hosted capability is first requested, the provider registry examines
credential-free remote candidates and returns one of:

- no applicable provider;
- one unambiguous candidate, ready for provider resolution;
- several candidates requiring an explicit repository choice; or
- a typed invalid or identity-conflict result.

The adapter resolves the candidate to a stable opaque repository ID and records the
source attachment. `origin` is a preference only when it is the single applicable
candidate; fork and upstream remotes are not silently conflated.
Provider resolution, authentication, and refresh never mutate the checkout.

Activation then proceeds independently:

```text
recognized source
  → stable provider binding
  → resource profile enabled
  → provider observation available
  → selected Git objects available when a content view needs them
```

A local checkout can therefore gain a PR index and selected PR bundles without a full
managed repository store.
A repository opened from a URL and two independent local clones reuse the same provider
mirror once they resolve to the same `RepositoryRef` and authorization context.

## Coordinated Hosted Views

A hosted comparison lease pins all of the following:

- the provider resource-set and committed manifest snapshot;
- the repository store identity;
- the exact base, head, and optional merge object IDs; and
- verified local availability of the objects needed by the view.

Its selected-object acquisition is authorized by a Git credential lease whose
authorization-context key equals the provider observation’s, whether the fetch runs
during that acquisition or later when content is requested.
The persistent comparison lease contains only the non-secret authorization-context
identity; each short-lived Git credential lease lives only as long as the session that
registered it and the Git runs using it.

Provider-observed object identity and local object availability are separate facts.
A provider snapshot may know object ID `X` while the local store reports
`not_requested`, `present`, `missing_fetchable`, `fetch_failed`, `unavailable`, or
`outside_bound`. Fetching `X` does not rewrite the provider artifact.
If a provider ref moves between API observation and Git fetch, publication verifies the
fetched ref still matches `X`; otherwise it reacquires or reports the stale/unavailable
state. It never combines metadata for one object with content from another.

## Locks and Deletion

The fixed lock order is:

1. application-home lock for layout migration and global enumeration;
2. source-alias lock for alias creation; and
3. one or more repository-store locks in ascending `RepositoryStoreId` order for store
   directory publication and store records.

Network work and long-running Git processes hold none of these locks, and a local
checkout is never a lock target.
A refresh instead holds its store’s fetch side lock,
`locks/stores/<store-key>.fetch.lock`, across the fetch.
It is only tried without blocking: a refresh that finds it busy reports that another
refresh is running and does not wait.
The Git processes that write the store inherit the lock’s descriptor, so it stays held
for as long as any of them runs, even when the server that took it was killed; Ctrl-C’s
immediate exit kills those process groups first, and a graceful shutdown cancels them
through the lifespan.
The helpers a fetch starts inherit it too (`upload-pack` and `index-pack`, and over
HTTPS the remote helper and its credential helper), and they end with the fetch.
Nothing longer-lived does: every store sets `gc.auto=0` and `maintenance.auto=false`, so
a fetch never leaves a detached gc or maintenance run holding the lock after it.
Every writer of a published store therefore holds the lock while it lives, so lock
files, temporary objects, and temporary packs a killed fetch left in the store are
removed under it before the next fetch.
The refresh takes the store lock only to rewrite `state.yml`. Acquisition takes the
alias lock and then the store lock and holds both from the store’s rename through the
alias commit, so every alias that names a store is written under that store’s lock.
`tests/test_cache_publish.py` checks that the real acquisition holds both at the store
rename, the alias write, and the source rename.

Nothing deletes or moves a published store or source.
A reader reaches a store only through its alias and takes no lock, and nothing removes
objects from a store.
A store no alias names, which a crash between the two renames leaves, stays until the
next acquisition of its source reuses it.
The only deletion is the startup sweep: a staging entry carries a liveness lock that is
only tried without blocking, and the sweep deletes an entry whose lock is free.
Quarantine, trash, and automatic store reclamation were removed with the thin-mirror
Simplify step; a purge command for stores is deferred until after the alpha.

Every lock attempt uses its own `open()` of the lock file, and descriptors are never
shared or duplicated between holders, even in one process: `flock` belongs to the open
file description, and a request through a `dup()` of a held descriptor is granted
instead of contending.
No cache lock blocks the event loop, and `_acquire` in `locks.py` refuses a blocking
lock on a thread that runs one.
Opening the cache and publication each run as one synchronous section in a worker thread
and release their locks before returning.
The lock order, the side locks, the lock sequences, and the startup sweep’s state
machine are `tests/fixtures/repository-cache/state-machines.json`, and production
replays each of them.
`tests/test_repository_cache_contract_fixtures.py` runs the sequences through
`locks.py`, and `tests/test_cache_reclaim.py` checks every transition the real sweep
reports, with the locks it holds, against the machine.

### Acquisition and refresh state machines

The two machines below are the design `cache/acquire.py` and `cache/update.py` follow.
They are a record of that design and not data a test replays: the code does not report
these transitions, so nothing checks a table row against it.
The behavior is tested directly, and each machine names where.

A state is visible when an ordinary open, catalog scan, or served subject can observe
the entry or result it describes.
A state with no recovery is terminal.
The recoveries are in [After a crash](#after-a-crash).

#### Acquisition

Staging holds only its own liveness lock, the network work holds no hierarchy lock, and
publication holds the alias lock and the store lock together.

| From | Event | To | Locks held | Network | Effect |
| --- | --- | --- | --- | --- | --- |
| `absent` | `claim_staging` | `staging_claimed` | `staging_entry` | no | Take `locks/staging/<entry>.lock`, then create `staging/<entry>/` on the cache filesystem. |
| `staging_claimed` | `lookup_remote_head` | `head_observed` | `staging_entry` | yes | `git ls-remote --symref origin HEAD` records the remote default branch and its object ID. |
| `staging_claimed` | `remote_unavailable` | `abandoned` | `staging_entry` | no | Typed failure; staging deleted. |
| `head_observed` | `fetch_started` | `fetching` | `staging_entry` | yes | `init --bare --template=`, Metabrowser-written config with automatic maintenance and gc off, then a fetch with explicit refspecs. HTTPS uses the 1,000 bytes/s for 30 s low-speed policy and the fetch has a 900 s deadline; the user can also cancel. An overlay adds its two configuration keys, its alternates file, and its boundary link first, and the fetch its negotiation tips. |
| `fetching` | `fetch_failed` | `abandoned` | `staging_entry` | no | Typed failure; staging deleted. |
| `fetching` | `cancelled` | `abandoned` | `staging_entry` | no | Git terminated (4.4 ms to exit after SIGTERM, `explorations/repository-cache/results/concurrency.json`); staging deleted. |
| `fetching` | `fetch_succeeded` | `fetched` | `staging_entry` | no | Fetched objects are available through the staging store’s own object directory and, for overlays, its admitted lender; shallow boundaries remain explicit. |
| `fetched` | `validation_failed` | `abandoned` | `staging_entry` | no | The observed HEAD object, its branch, or the object format did not validate; staging deleted. |
| `fetched` | `validated` | `validated` | `staging_entry` | no | Write `store.yml` with acquisition metadata and the optional lender, and `state.yml` with the default ref/revision, fetch time, and acquisition outcome. |
| `validated` | `publish_store` | `store_published` | `source_alias`, `repository_store`, `staging_entry` | no | Take the alias lock, then the store lock, and keep both through the alias commit; verify the store directory is absent and rename staging into `repository-stores/<store-key>`. |
| `validated` | `store_exists_same_identity` | `store_reused` | `source_alias`, `repository_store`, `staging_entry` | no | Under the same two locks, a concurrent acquisition had published the same deterministic store first; its records validate, and staging is deleted after the locks are released. |
| `store_published` | `publish_alias` | `alias_published` | `source_alias`, `repository_store`, `staging_entry` | no | Still under both locks, atomically create `sources/<slug>/` with `source.yml` and `store-alias.yml` as the sole visibility commit; release both locks. |
| `store_reused` | `publish_alias` | `alias_published` | `source_alias`, `repository_store`, `staging_entry` | no | Same visibility commit. |
| `store_published` | `alias_exists_same_store` | `alias_published` | `source_alias`, `repository_store`, `staging_entry` | no | Another process committed the identical alias first; release both locks. |
| `store_reused` | `alias_exists_same_store` | `alias_published` | `source_alias`, `repository_store`, `staging_entry` | no | Another process committed the identical alias first; release both locks. |
| `store_published` | `alias_points_elsewhere` | `alias_conflict_reported` | `source_alias`, `repository_store`, `staging_entry` | no | The existing alias stays; release both locks, leaving the new store unreferenced. |
| `store_reused` | `alias_points_elsewhere` | `alias_conflict_reported` | `source_alias`, `repository_store`, `staging_entry` | no | The existing alias stays; release both locks. |

| State | Visible | After a crash |
| --- | --- | --- |
| `absent` | no | `nothing_to_recover` |
| `staging_claimed` | no | `staging_swept` |
| `head_observed` | no | `staging_swept` |
| `fetching` | no | `staging_swept` |
| `fetched` | no | `staging_swept` |
| `validated` | no | `staging_swept` |
| `store_published` | no | `unreferenced_store_kept` |
| `store_reused` | no | `unreferenced_store_kept` |
| `alias_published` | yes | terminal |
| `alias_conflict_reported` | yes | terminal |
| `abandoned` | no | terminal |

`tests/test_cache_publish.py` records the locks the real acquisition holds at the store
rename, the alias write, and the source rename.
`cli-cache-interrupt-store.txt` and `cli-cache-interrupt-alias.txt` kill a process
before each publication and show what the next acquisition finds, and
`cli-cache-fetch-failures.txt` shows the abandoned paths.

#### Refresh

The fetch side lock is held from the first step to the last, and the store lock is taken
under it only to rewrite `state.yml`.

| From | Event | To | Locks held | Network | Effect |
| --- | --- | --- | --- | --- | --- |
| `published` | `take_fetch_lock` | `fetch_locked` | `store_fetch` | no | Try `locks/stores/<store-key>.fetch.lock` without blocking. |
| `published` | `fetch_lock_busy` | `refreshing_elsewhere` | none | no | Another holder is refreshing the store; report it and fetch nothing. |
| `fetch_locked` | `remove_stale_locks` | `locks_cleaned` | `store_fetch` | no | Remove `packed-refs.lock`, `refs/**.lock`, temporary loose objects, and temporary packs a killed Git left in the store. Every writer of the store holds this lock, through the descriptor it inherited, so none of them is live. |
| `locks_cleaned` | `lookup_remote_head` | `head_observed` | `store_fetch` | yes | `git ls-remote --symref -- origin HEAD` records which branch the origin’s HEAD names. |
| `locks_cleaned` | `remote_unavailable` | `failure_recorded` | `repository_store`, `store_fetch` | no | Typed failure; under the store lock, `state.yml` records a failed refresh and keeps the previous fetch time and default revision. |
| `head_observed` | `fetch_started` | `fetching` | `store_fetch` | yes | `git fetch --prune --atomic --no-write-fetch-head origin` with the branch and tag refspecs, in Git’s own process group, holding the inherited fetch lock. |
| `fetching` | `fetch_refused` | `pruning` | `store_fetch` | no | Git ran and failed, and no ref moved. One transaction cannot delete `side` and create `side/x`, or rename `Topic` to `topic` on a case-insensitive file system, and Git words that refusal differently for loose refs, packed refs, and reftable, or pushes it past the bounded stderr, so every such failure is followed by the prune. |
| `fetching` | `fetch_failed` | `failure_recorded` | `repository_store`, `store_fetch` | no | Git could not start or was stopped at its deadline, which a prune cannot help. No ref moved, because the fetch is atomic; under the store lock, `state.yml` records the failed refresh and keeps the previous fetch time and default revision. |
| `pruning` | `stale_refs_pruned` | `refetching` | `store_fetch` | yes | `git remote prune` with the mirror refspecs deletes the refs whose branch or tag the origin no longer has, and nothing else; the atomic fetch then runs once more. |
| `pruning` | `prune_failed` | `failure_recorded` | `repository_store`, `store_fetch` | no | The prune may have deleted some stale refs before it failed. Under the store lock, `state.yml` records the failed refresh with the origin’s default branch or the one recorded before, whichever the mirror still has, and keeps the previous fetch time. |
| `pruning` | `cancelled` | `cancelled` | `store_fetch` | no | Git’s process group is killed; each ref deletion is whole, stale refs already deleted stay deleted, and the record is left as it was. |
| `refetching` | `fetch_succeeded` | `fetched` | `store_fetch` | no | With the stale refs gone, every branch and tag moved together. No object was removed. |
| `refetching` | `fetch_failed` | `failure_recorded` | `repository_store`, `store_fetch` | no | The second transaction moved no ref, but the prune deleted stale refs. Under the store lock, `state.yml` records the failed refresh with the origin’s default branch or the one recorded before, whichever the mirror still has, and keeps the previous fetch time. |
| `refetching` | `cancelled` | `cancelled` | `store_fetch` | no | Git’s process group is killed; the second transaction moved every ref or none, stale refs the prune deleted stay deleted, and the record is left as it was. |
| `fetching` | `cancelled` | `cancelled` | `store_fetch` | no | Git’s process group is killed, by the lifespan’s cancellation or by the command’s immediate exit; the atomic fetch moved every ref or none, and the record is left as it was. |
| `fetching` | `fetch_succeeded` | `fetched` | `store_fetch` | no | Every branch and tag moved together; branches and tags deleted upstream were pruned. No object was removed. |
| `fetched` | `validation_failed` | `failure_recorded` | `repository_store`, `store_fetch` | no | The origin’s default branch is missing from the mirror or is not a commit; the failure is recorded under the store lock. |
| `fetched` | `record_written` | `recorded` | `repository_store`, `store_fetch` | no | Under the store lock, `state.yml` gets the default branch, its commit, the fetch time, and the succeeded outcome; then both locks are released. |

| State | Visible | After a crash |
| --- | --- | --- |
| `published` | yes | `nothing_to_recover` |
| `fetch_locked` | yes | `nothing_to_recover` |
| `locks_cleaned` | yes | `nothing_to_recover` |
| `head_observed` | yes | `nothing_to_recover` |
| `fetching` | yes | `fetch_interrupted` |
| `pruning` | yes | `prune_interrupted` |
| `refetching` | yes | `fetch_interrupted` |
| `fetched` | yes | `record_behind` |
| `recorded` | yes | terminal |
| `failure_recorded` | yes | terminal |
| `refreshing_elsewhere` | yes | terminal |
| `cancelled` | yes | terminal |

`tests/test_cache_update.py` drives each path against a real mirror: a refresh that
succeeds, one that finds the fetch lock busy, a removed origin, a clash that is pruned
and retried, a retry that still fails, a cancelled fetch, and the leftovers of a killed
one. `RefreshOutcome` in `cache/update.py` is what a refresh reports.
It has outcomes this machine does not model, such as `ref_case_collision`, and the
module’s own description is the authority for those.

#### After a crash

The startup sweep’s machine is in the fixture and has no states table here.
It changes nothing durable before it lists the staging entries, and a crash in any state
after that is `sweep_restarts`.

| Recovery | Visible afterwards | What happens |
| --- | --- | --- |
| `nothing_to_recover` | unchanged | No durable state changed before the crash. |
| `staging_swept` | no | The startup sweep finds the staging entry’s lock free and deletes the entry. A SIGKILLed clone leaves its destination and a temporary pack behind (`explorations/repository-cache/results/concurrency.json`), so staging is never inside a published path. |
| `unreferenced_store_kept` | no | The crash released the acquisition’s locks after its store was published and before its alias was. A published store that no alias names is not visible. It stays in place, and the next acquisition of the same source reuses it and publishes the alias. |
| `sweep_restarts` | unchanged | The sweep is idempotent and runs again at the next startup. |
| `fetch_interrupted` | unchanged | The atomic fetch moved every ref or none, and objects it wrote stay unreferenced. A killed Git can leave `packed-refs.lock`, `refs/**.lock`, a temporary loose object, or a temporary pack; the next refresh removes them under the store’s fetch lock before it fetches, which it can take only once no Git from the interrupted refresh is alive. `state.yml` still records the previous fetch. |
| `prune_interrupted` | unchanged | Some refs whose branch or tag the origin deleted are gone and others are not; each deletion is whole, and no commit is removed. The next refresh prunes the rest. |
| `record_behind` | unchanged | The refs moved but `state.yml` still names the previous default revision and fetch time. Nothing reads the record to find a commit, and the next refresh rewrites it. |

## Implementation Seams

These file- and function-level boundaries are split by state.
Neither table registers a surface, so neither carries a check; registered surfaces are
in [Views, Models, and Routes](arch-views-models-routes.md).

### Implemented seams

| Area | Implemented at | Responsibility |
| --- | --- | --- |
| Subject and Git target | `source.py`: `RepositorySubject`, `AttachedFilesystemSubject`, `SourceSession`; `git/tree_source.py`: `GitRevisionSubject`; `git/process.py`: `GitCommandTarget`, `GitLocation`, `run_git`, `run_git_at`, `spawn_git_process` | Separate session selection from a filesystem path. `metab` can `--show`, non-cache `--api`, or `--check-api` a `file://` pin in-process, and serve it |
| Content source | `source.py`: `SourceCapabilities`, `ContentSource`, `ContentHandle`, `FilesystemContentSource`; `inventory_engine/coordinator.py`: `open_subject`; `cli/git_pin_cli.py`: `file://` pin; `git/tree_source.py`: `GitTreeSource` | One capability-gated content contract for an attached filesystem and an immutable revision, with no invented mtime, ignore state, or watcher. Inventory open on a Git pin leaves the walker closed and reports a complete-at-once index. What each route answers on a pin is in [Git and Comparison Sources](arch-git-and-comparison-sources.md) |
| Plugin content reader | `plugin_api.py`: `resolve_content`, `resolve_content_container`, `stat_content`, `read_content_window`, `ContentRef`, `ContentStat`, `ContentWindow`; `source.py`: `FilesystemContentSource.open_ref`, `read_artifact_window`; `git/tree_source.py`: `GitTreeSource.open_ref`, `blob_logical_ext`; `content_errors.py`: `ContentReadError`, `ContentUnavailableError` | One bounded, source-agnostic read for plugin data hooks over an opaque `ContentRef`, with every read taking an explicit byte maximum and no unbounded variant, filesystem work in the thread pool and pinned reads through the pooled `cat-file` actors, and one catchable failure family carrying the `code` and `http_status` the pinned routes answer with. The four built-in data hooks that read bytes hold no Git import and no source-kind branch |
| Plugin and route bridge | `plugin_api.py`: `open_content`, `source_capabilities`, `require_source_capability`, filesystem-only path helpers; `server.py`, `events_route.py`, `git/routes.py`, `git/content_routes.py`, `git/repo.py`, `git/history.py`; `diff/adapters/git.py`: `GitDiffSource`; `builtin_plugins/diff/sidekick.py`: comparison, document, and children hooks; `builtin_plugins/binary/sidekick.py`: chunk hook; `builtin_plugins/structured`: parsed hook; `builtin_plugins/agent_log/sidekick.py`: charts hook; `plugin_loader/classify.py`: `classify_identity` | Resolve the active content-source handle rather than assuming the global root is a `Path`; capability-gate recency, ignore, watcher, activity, mutation, and Git listing sizes; honor a pinned `GitRevisionSubject` on Git collection, file, raw, tree, rollup, catalog, index status, capabilities, tree filter tallies, tree summary, filtered tree totals, include_ignored no-op, tree depth, file envelope ext, markdown frontmatter, text preview window, in-tree symlink follow including plugin sidekicks, diff-comparison including `GitDiffSource.content`, KPress, patch-file container, binary-chunk, identity-and-content-kind, structured-parsed, and agent-log routes, and image preview; keep route, CLI, and golden parity |
| Revision tree | `git/tree_source.py`: `GitPath`, `GitTreeSource`, `GitRevisionSubject`, `list_tree`, `read_blob`; shared per-store `cat-file --batch-command --buffer` pool (`MAX_BATCH_READERS_PER_STORE`); `git/content_routes.py`: file, raw, tree, catalog, `split_git_container_wire`, and extension plugin kinds | Enumerate NUL-framed byte-safe full-OID trees and read size-gated blobs from a `RepositoryStoreTarget` with no materialization. `GitPath` wires are the identity on every route that accepts one, and blob kinds come from extension, basename, sniffed adapter, and bounded JSON/YAML/frontmatter mappings. The per-route projections are in [Git and Comparison Sources](arch-git-and-comparison-sources.md) |
| Repository store | `cache/repository_store.py`: `open_revision`; `cache/records.py`: source aliases and store state; `cache/acquire.py`: `acquire_source`; `cache/reclaim.py`: staging sweep | `open_revision` checks that a commit is in the published store and returns its `GitRevisionSubject`, writing nothing and holding no lock. Acquisition reuses a healthy published store. On a cache miss it borrows from an admitted checkout or makes a full clone of the `file://` or `https://` source, then publishes the store and its alias under the alias and store locks. Nothing deletes a published store |
| Serving a pin | `source.py`: `serve_subject_opener`, `lifespan_subject`, `attach_owned_subject`, `close_owned_subject`; `server.py`: `_lifespan`, `_pin_label_html`; `cli/git_pin_cli.py`: `run_serve_pin`; `source_routes.py`: `source_status` | Serve mode acquires, resolves what the URL selects, proves that pin opens, and hands the server an opener, because a pin’s batch readers belong to the event loop that started them. The application lifespan opens the pin in the serving loop before the inventory reads the subject, attaches it, and closes whichever pin is served at shutdown; each start opens a fresh pin. `/api/source/status` and the navigation heading report the pin and the ref it was resolved from, a pull-request URL’s number, and for a served mirror the repository’s name, its origin, and where the mirror is kept ([What a mirror’s page is called](#what-a-mirrors-page-is-called-and-where-it-says-it-is-kept)). On a served pin the cache routes and the `/raw/<path>` form answer `unsupported_for_subject`, and the untrusted profile is forced |
| Refresh and pin switching | `cache/origin.py`: `ls_remote_head_args`, `mirror_fetch_args`, `mirror_prune_args`, `classify_remote_failure`; `cache/update.py`: `update_store`, `remove_interrupted_fetch_leftovers`; `locks.py`: `store_fetch_lock`; `cache/resolve.py`: `resolve_pin`, `resolve_selection`, `ref_tip`, `list_mirror_refs`; `cache/served_mirror.py`: `StoreMirror`, `repository_name`, `display_directory`; `mirror_refresh.py`: `RefreshCoordinator`, `MirrorSession`, `serve_mirror`, `lifespan_refresh`; `source.py`: `replace_owned_subject`; `source_routes.py`: `api_source_refresh`, `api_source_pin`, `api_source_refs`, `view_on_pin`, `SourcePinGuard`; `static/source-freshness.js`, `static/source-pin-guard.js`, `static/source-ref-selector.js` | One fetch per refresh under the store’s fetch side lock, from the source’s URL, with typed outcomes, which the Git processes inherit so it stays held while any of them runs. The coordinator keeps background jobs on the application state keyed by store key, joins concurrent requests, runs at most two at once, and cancels them at shutdown; a Ctrl-C kills their process groups before it exits. Status freshness is answered from memory. One resolver serves URL opening and the pin route: exact ref names from one `for-each-ref` (branch, then tag, then commit ID). The ref selector lists the mirror’s branches or tags from one more `for-each-ref`, filtered and bounded in the route, and a switch that names the page’s `/view/` address answers where that page goes on the new pin. A pin replaces the served subject under a new generation, attaching the new subject before closing the old, so no request meets a moment with nothing served. In a server, a selection the mirror lacks starts one background fetch and answers `selection_pending`, then the switch or not found; a URL selection the mirror lacked at startup is served when that fetch brings it, under a new generation like any switch. The lifespan’s opener is left alone, so a restart serves the pin the banner announced. Serve mode refreshes a stale mirror once at startup and follows a refresh another process is running until it ends. One-shot URL startup may acquire the source and obtain missing PR metadata or required Git refs; after URL selection resolves, ordinary cache-only reads do not fetch, while explicit refresh actions may. Any failure of the atomic fetch is followed by a prune of stale refs on their own and one more try, which clears a ref clash (`side` becoming `side/x`, a case-only rename) however Git words it; a clash that remains on a case-insensitive store, or a fetch that folded one ref into its case twin, puts every ref back and is `ref_case_collision`. A page on a pin names the commit it shows on its `fetch` data requests (`static/source-pin-guard.js`), and `SourcePinGuard` refuses another commit with `pin_changed`; the commit rather than the session generation is the token because a generation restarts at 1 in every server process. Back and forward bring such a page back from the browser’s caches without asking, so on a history landing the same script asks the status route once and reloads the page, at most once, when another commit is served; the page stays cacheable, so a landing with nothing switched keeps the back/forward cache and its scroll position. A commit pinned by ID is served under the ref last served, or the served pull request’s head ref, when it is that ref’s tip, so a switch away and back by ID stays on the ref |
| Remote discovery | `repository_context.py`: `discover_repository_context` | Read a checkout’s `origin` remote and `HEAD` without running Git, so a provider candidate can be recognized before any network work |
| Providers and GitHub URLs | `cache/providers.py`: `RepositoryProvider`, `url_reducers`, `provider_git_config`, `check_first_clone`, `repository_context_for`, `open_pull_request`; `builtin_plugins/github/`: `GithubUrlReducer`, `GithubProvider`, `run_gh`; `cache/urls.py`: `RepositorySelection`, `ReducerRejection` | Core names no provider. The GitHub reducer turns web, raw, and SSH URLs into the canonical source plus a selection, or a typed refusal; the provider supplies the `gh` credential helper, the first-clone size check, a mirror’s `repository_context`, and the head a pull-request URL pins |
| Pull-request records | `builtin_plugins/github/gh.py`: `gh_api`, `gh_account`; `builtin_plugins/github/pulls.py`: `refresh_pull_request`, `open_pull_request`; `builtin_plugins/github/pull_record.py`: `PullRecord`, `read_pull_record`, `write_pull_record`; `builtin_plugins/github/sidekick.py`: `pull_handler`, `pull_refresh_handler`; `builtin_plugins/github/pull_route.py`: `pull_envelope`, `pull_host`, `start_refresh`; `builtin_plugins/github/served_pull.py`: `ServedPull`, `ServedPulls`; `mirror_refresh.py`: `CompanionRefresh`, `PullRequestSet`, `MAX_PULL_JOBS`; `cache/pull_refs.py`: `fetch_pull_head`, `comparison_endpoints` | Read a pull request with bounded, conditional `gh api` pages, fetch `refs/pull/<n>/head` under the store’s fetch side lock, compute the merge-base endpoints, and keep one record per pull request; serve it from the cache alone, and refresh it in the refresh coordinator beside the mirror. See [Pull-request records](#pull-request-records) |
| Ref and path resolution | `cache/resolve.py`: `ref_candidates`, `resolve_ref_and_path`, `resolve_commit_id`, `resolve_selection` | Split a URL’s ref-and-path by what the mirror has, with `show-ref --verify` per candidate and no user text in `rev-parse` revision syntax; report whether one fetch could change a miss |
| File and raw routes | `view_routes.py`, `server.py`, `git/content_routes.py`, `plugin_api.py`; `static/navigation.js`: `displayPath` | Resolve the active content-source handle rather than assuming the global root is a `Path`; Git subjects use `GitPath` wire identities for `/view/`, file, raw, tree, KPress, patch-file containers, identity-and-content plugin kinds, structured parsed, agent-log JSONL, and image preview; Markdown and wiki links on a pin encode authored segments as `GitPath` wires; SPA path chrome decodes those wires to display names (C0 and invalid UTF-8 become U+FFFD); retain route, CLI, and golden parity for filesystem browsing |

### Planned seams

Nothing below is built, and none of it is on the v0.12 path.
The thin-mirror plan retired the provider mirror and provider ports.
Checkout PR browsing uses the store-backed path described above; these broader provider
abstractions remain future work.

| Area | Planned boundary | Responsibility |
| --- | --- | --- |
| Source attachments | A neutral provider-resources module for source binding and local-availability records | Map local and managed sources to stable provider repository identity without storing local paths or requiring a cache entry. `ProviderBinding`, `LocalGitObjectAvailability`, `AuthorizationContextRef`, and `authorization_context_key` are specified in [Hosted Review Model and Provider Boundary](arch-hosted-review-model.md) |
| Provider mirror | `provider_resources/store.py`: `stage_snapshot`, `publish_manifest`, `read_current`, `read_last_complete`, `lease_snapshot`, `reclaim_snapshots` | Publish one repository-scoped, auth-scoped mirror reused by every attachment |
| Provider ports | `plugin_api.py`: opaque `GitFetchCredentialLease`, `provider_fetch_authorization_context`, `RepositoryContentPort.open_subject`, `RepositoryObjectJobPort.request_selected_refs`, `ProviderResourceStorePort.stage`, `publish`, `read`, `lease` | Inject narrow cancellable capabilities with typed unavailable, authorization, stale-generation, and publication failures; selected-ref requests carry a non-secret context plus an unforgeable registry handle, never tokens, unrestricted sources, core stores, or paths |

These names are a design record, not registered surfaces.
If implementation finds a smaller boundary that preserves every invariant, the
architecture and beads are updated before code publication.

## Phased Delivery

Phases 2 to 4 are implemented.
Phase 1’s binding and storage contracts were built and then removed with the
hosted-review code. Phase 6 is implemented for a directly opened pull request, as the
GitHub plugin’s own records rather than provider-mirror snapshots.
Discovery, navigation, and checkout-backed PR comparisons are implemented through the
[Pulls tab plan](../specs/active/plan-2026-10-01-github-pulls-tab.md); the original
provider-neutral mechanisms are not.
Phase 7 remains later work.

1. Correct the unreleased binding and storage contracts so provider repository identity
   is independent of a generic cache entry.
2. Introduce `SourceSession`, repository subjects, capabilities, and the attached-
   filesystem content adapter with no visible behavior change.
3. Add `GitCommandTarget`, the immutable Git-tree content source, and full-OID tree/blob
   routes.
4. Publish the untrusted-content profile, then open repository URLs as immutable
   subjects and add selected-branch resolution in a separate phase.
5. Attach user-owned repositories to shared provider mirrors and lazily fetch selected
   refs into the shared repository store.
6. Add direct PR cache and views, then bounded PR discovery and navigation.
7. Apply the same resource-profile, mirror, and view contracts to releases and later
   providers.

Each phase is one formal stacked pull request with its own review, complete
verification, and green CI before the next phase is eligible to land.

## Acceptance Rules

The architecture is satisfied only when tests prove:

- two concurrent processes browse different full object IDs from one repository store
  without any checkout, index, branch switch, or worktree directory;
- one server exposes exactly one active subject generation, while two processes can
  browse different subjects and share the store without cache or event cross-talk;
- a dirty attached checkout remains byte-for-byte unchanged while provider data and refs
  refresh;
- an acquired store is complete: every read family answers from it with its origin
  deleted, and no read changes its objects;
- a crash between a store’s publication and its alias leaves an unreferenced store that
  the next acquisition of the source reuses, and no alias ever names an absent store;
- a valid cached view opens while another client refreshes, and failed refresh leaves
  the prior validated observation available;
- purging one source does not remove a store another alias names;
- cancellation mid-blob, an oversized blob, a missing blob, invalid UTF-8, a newline in
  a Git name, a symlink, and a gitlink all produce the specified bounded result without
  desynchronizing another reader; and
- every new route, model, persisted state, and browser interaction has `metab` parity,
  exact goldens, and an architecture-map entry when it becomes registered.

The thin-mirror plan’s
[Testing](../specs/active/plan-2026-09-23-v012-thin-mirror.md#testing) section owns
acceptance for HTTPS, refresh, GitHub authentication, and pull-request data.

## Measured Decisions

Phase 0 measured these choices on 2026-09-16; the method, environment, and raw results
are in
[Repository cache measurements](../../../explorations/repository-cache/README.md), and
the complete decision table is
[Phase 0 decisions](../specs/active/plan-2026-08-11-open-repo-from-git-url.md#phase-0-decisions).
The numbers come from one macOS machine with Git 2.50.1 and explain each choice; they
are not budgets.

- **Bare layout.** Bare and no-checkout stores cost the same to acquire and store,
  within run-to-run variation, but a no-checkout store keeps `core.bare=false`, an empty
  work tree, reflogs, and a local branch.
  The store is created with `git init --bare`, and refs arrive through explicit
  refspecs: branches under `refs/remotes/origin/`, and tags.
- **No mailmap on store reads.** With Git defaults, history and commit reads loaded
  `HEAD:.mailmap`, and with lazy fetch disabled they printed an error and exited 0.
- **Automatic maintenance disabled, umask `077`.** Each fetch, including each lazy
  fetch, spawned `git maintenance run --auto`; over HTTPS the 51st consecutive lazy
  fetch then failed with a commit-graph error.
  Under umask `022` Git wrote group- and world-readable store files; under `077` none.
- **Four readers per store.** Whole-tree reads peaked at four batch readers and fell
  with eight. Cancellation terminates a reader (exit within 0.77 ms) and a replacement
  answers in about 9 ms, so there is no in-band cancel.
- **Shared store for concurrent subjects.** Readers of different object IDs ran
  concurrently with byte-identical output, and readers saw no failure across
  `repack -a -d` and `gc --prune=now`.
- **`flock`, lock-based liveness, and locked no-replace publication.** A killed `flock`
  holder released in 2.8 ms, a `lockf` lock vanished when an unrelated descriptor
  closed, and `os.rename` replaced an empty directory.
  Publication verifies absence under the owning lock and uses
  `renameat2(RENAME_NOREPLACE)` or `renamex_np(RENAME_EXCL)` as defense in depth.
  The lock order is `tests/fixtures/repository-cache/state-machines.json`, and the
  acquisition and refresh machines are in
  [Locks and Deletion](#acquisition-and-refresh-state-machines).

The thin-mirror plan reversed the choices that served partial clones on 2026-09-23.
Their measurements stay in the exploration as the record to revisit:

- **Blobless acquisition with default-revision prefetch.** Serving the default
  revision’s tree took 5.8–5.9 s blobless against 8.8–17.8 s full for `python/mypy` over
  HTTPS. Fresh acquisition without an admitted lender remains a full clone; borrowed
  stores are covered separately above.
  Blobless acquisition remains future work.
- **Generic convergence and recorded promisor remotes.** The former partial-clone
  convergence design remains retired.
  Borrowed stores can lose objects when their lender changes; their explicit, bounded
  recovery can request observed object IDs.
  That path does not restore a promisor remote or background full-store convergence.
- **No implicit lazy fetch.** `GIT_NO_LAZY_FETCH=1` stays set on every store read.
  Missing borrowed objects remain visible as unavailable until explicit network work
  repairs them, when the origin can still supply them.
- **Generic durable and job refs.** The former convergence scheme remains retired.
  Current PR acquisition keeps its fetched pull ref, and an overlay sweeps refs whose
  borrowed objects disappeared before fetching.
  This is separate from garbage collection of a full store’s own objects; fetch work
  remains serialized per store.

Still open, with owners:

- tree-index and immutable directory-index bounds, which need browser measurements
  (Phase 1B-c);
- the refresh age over HTTPS: the one-minute window is measured over `file://` only (the
  thin-mirror plan). Contention between processes is reported as `refreshing_elsewhere`,
  never waited on or retried;
- size accounting and a purge command for repository stores, which the thin-mirror plan
  defers until after the alpha;
- lock, rename, and case semantics beyond macOS: CI runs only on Linux, so Phase 1A adds
  a runtime probe at application-home setup that refuses a home whose locks or
  no-replace publication do not behave as frozen;
- an origin ref whose name is decomposed (NFD) on a macOS store: the first refresh
  lands, but Git’s `remote prune` precomposes the name while `fetch --prune` does not,
  so later refreshes meet a ref-lock clash and report `ref_case_collision`; and
- whether distribution Git builds that backport the security fixes under an older
  version string are admitted (Phase 1B-a).

The initial-acquisition stall bound, the first-request deadline, and the first-clone
size limit were measured on 2026-09-23, and the size limit again on 2026-11-02; each
measurement is recorded beside its constant in `cache/origin.py` and
`builtin_plugins/github/provider.py`. `METABROWSER_MAX_FIRST_CLONE_KB` moves the size
limit, and the acquisition deadline still applies.

These choices may tune cost.
They may not introduce shared working-tree state, make a local checkout cache authority,
or weaken immutable publication.

## References

- [git-cat-file](https://git-scm.com/docs/git-cat-file) documents the batch object-read
  protocol used by immutable revision sources.
- [git-ls-tree](https://git-scm.com/docs/git-ls-tree) documents tree enumeration without
  a checkout.
- [Partial clone](https://git-scm.com/docs/partial-clone) defines the
  object-availability model evaluated before choosing full clones.
- [git-maintenance](https://git-scm.com/docs/git-maintenance) documents the repository
  maintenance that stays off in every store.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
