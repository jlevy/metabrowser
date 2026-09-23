# Repository Sources and Provider Mirrors

**Superseded in part (2026-09-23):** planned fetch jobs, credential handling, and
provider mirrors below are replaced by
[Thin Mirror for Git and GitHub Browsing](../specs/active/plan-2026-09-23-v012-thin-mirror.md).
Revision leases, subject refs, convergence, and store reclamation are removed from the
code and from this document.

**Status:** Partly implemented.
Repository subjects, `SourceSession`, capabilities, the attached-filesystem content
source, `GitCommandTarget`, the immutable Git tree source with `GitPath` file, raw, and
tree routes, and `file://` acquisition of full clones into a shared, read-only
repository store are implemented; `metab` opens a `file://` pin in-process for `--show`,
non-cache `--api`, and `--check-api`, and serves it over HTTP under the forced untrusted
profile. A served store refreshes from its `file://` origin in the background, and a
server can switch its pin to another branch, tag, or commit of the same store.
`https` acquisition and pull-request data remain planned, and
[Thin Mirror for Git and GitHub Browsing](../specs/active/plan-2026-09-23-v012-thin-mirror.md)
replaces the planned parts of this document wherever they disagree.
It retired blobless clones and convergence, private subject refs, revision leases,
maintenance locks, fetch jobs, and credential leases; this document no longer describes
them.
Provider binding and local object-availability records exist today as hosted-review
models; see [Hosted Review Model and Provider Boundary](arch-hosted-review-model.md).
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

## Shared Repository Store

One logical repository store owns one worktree-free Git database: a read-only mirror of
its origin. It is a bare repository created with an empty template and configuration
written only by Metabrowser, with automatic maintenance and `gc` off, and filled by one
fetch of every object reachable from the origin’s branches and tags, a full clone.
These invariants hold for every store:

- there is no shared index or checked-out branch;
- no view operation runs `checkout`, `switch`, `reset`, or `worktree add`;
- its refs are the origin’s branches under `refs/remotes/origin/` and its tags;
  Metabrowser writes no ref of its own;
- repository content is self-contained: every object is present, and nothing depends on
  alternates into a user-owned checkout or on the origin after acquisition;
- tree enumeration and blob reads are bounded and cancellation-aware; and
- nothing removes objects: no operation runs `gc`, `prune`, or `repack`, so a commit a
  reader pinned stays readable without a lock or a ref.

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
Attaching a user-owned checkout to a store, and merging stores by provider identity, are
deferred by the thin-mirror plan.

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
Diff, commit-detail, and comparison reads run Git directly, because a full store holds
every blob they read.
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

Only `file://` is fetched: acquisition, and refresh of a published store.
A refresh is `ls-remote --symref -- origin HEAD` for the default branch, then
`fetch --prune --atomic --no-write-fetch-head` of every branch and tag, so every ref
moves together or none does and a branch or tag deleted upstream leaves the mirror while
its commits stay. `cache/origin.py` builds both commands’ arguments for acquisition and
refresh alike; the thin-mirror plan adds HTTPS there, with `gh` as the only credential
helper for a private fetch.
Every fetch runs in the isolated Git environment of `git/process.py`, the only Git
subprocess boundary: no inherited `GIT_*` variable, no system or global configuration,
terminal prompting disabled, and hooks off.
Acquisition never inherits an attached checkout’s remote or credential helper.

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
2. source-alias lock for alias creation;
3. one or more repository-store locks in ascending `RepositoryStoreId` order for store
   directory publication and store records; and
4. provider-resource lock, whose use belongs to the provider plan.

Network work and long-running Git processes hold none of these locks, and a local
checkout is never a lock target.
A refresh instead holds its store’s fetch side lock,
`cache/locks/stores/<store-key>.fetch.lock`, across the fetch.
It is only tried without blocking: a refresh that finds it busy reports that another
process is refreshing the store and does not wait.
Every writer of a published store holds it, so lock files and temporary packs a killed
fetch left in the store are removed under it before the next fetch.
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
No cache lock blocks the event loop, and `_acquire` in `cache/locks.py` refuses a
blocking lock on a thread that runs one.
Opening the cache and publication each run as one synchronous section in a worker thread
and release their locks before returning.
The lock order and state machines are
`tests/fixtures/repository-cache/state-machines.json`.

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
| Repository store | `cache/repository_store.py`: `open_revision`; `cache/records.py`: source aliases and store state; `cache/acquire.py`: `acquire_file_source`; `cache/reclaim.py`: staging sweep | `open_revision` checks that a commit is in the published store and returns its `GitRevisionSubject`, writing nothing and holding no lock. Acquisition fetches every object of a `file://` source and publishes the store and its alias under the alias and store locks. Nothing deletes a published store |
| Serving a pin | `source.py`: `serve_subject_opener`, `lifespan_subject`, `attach_owned_subject`, `close_owned_subject`; `server.py`: `_lifespan`, `_pin_label_html`; `cli/git_pin_cli.py`: `run_serve_pin`; `source_routes.py`: `source_status` | Serve mode acquires, proves the default pin opens, and hands the server an opener, because a pin’s batch readers belong to the event loop that started them. The application lifespan opens the pin in the serving loop before the inventory reads the subject, attaches it, and closes whichever pin is served at shutdown; each start opens a fresh pin. `/api/source/status` and the navigation heading report the pin and the ref it was resolved from. On a served pin the cache routes and the `/raw/<path>` form answer `unsupported_for_subject`, and the untrusted profile is forced |
| Refresh and pin switching | `cache/origin.py`: `ls_remote_head_args`, `mirror_fetch_args`; `cache/update.py`: `update_store`, `remove_interrupted_fetch_leftovers`; `cache/locks.py`: `store_fetch_lock`; `cache/repository_store.py`: `resolve_pin`, `ref_tip`; `cache/served_mirror.py`: `StoreMirror`; `mirror_refresh.py`: `RefreshCoordinator`, `MirrorSession`, `serve_mirror`, `lifespan_refresh`; `source.py`: `replace_owned_subject`; `source_routes.py`: `api_source_refresh`, `api_source_pin`; `static/source-freshness.js` | One fetch per refresh under the store’s fetch side lock, with typed outcomes. The coordinator keeps background jobs on the application state keyed by store key, joins concurrent requests, runs at most two at once, and cancels them at shutdown. Status freshness is answered from memory. A selection resolves in the mirror alone through `show-ref --verify` candidates (branch, then tag, then commit ID) and replaces the served subject under a new generation. Serve mode refreshes a stale mirror once at startup; one-shot modes never fetch unless asked |
| Remote discovery | `repository_context.py`: `discover_repository_context` | Read a checkout’s `origin` remote and `HEAD` without running Git, so a provider candidate can be recognized before any network work |
| File and raw routes | `view_routes.py`, `server.py`, `git/content_routes.py`, `plugin_api.py`; `static/navigation.js`: `displayPath` | Resolve the active content-source handle rather than assuming the global root is a `Path`; Git subjects use `GitPath` wire identities for `/view/`, file, raw, tree, KPress, patch-file containers, identity-and-content plugin kinds, structured parsed, agent-log JSONL, and image preview; Markdown and wiki links on a pin encode authored segments as `GitPath` wires; SPA path chrome decodes those wires to display names (C0 and invalid UTF-8 become U+FFFD); retain route, CLI, and golden parity for filesystem browsing |

### Planned seams

Nothing below is built.
Where a row names an existing module, the named functions are what that module still
lacks.

| Area | Planned boundary | Responsibility |
| --- | --- | --- |
| HTTPS acquisition and refresh | `cache/origin.py`: the transport allowlist and credential arguments; `cache/acquire.py` | Clone `https` sources and refresh them through the `file://` refresh path, with `gh` as the credential helper for a private fetch; the [thin-mirror plan](../specs/active/plan-2026-09-23-v012-thin-mirror.md) owns the design |
| Source attachments | A neutral provider-resources module for source binding and local-availability records | Map local and managed sources to stable provider repository identity without storing local paths or requiring a cache entry. `ProviderBinding`, `LocalGitObjectAvailability`, `AuthorizationContextRef`, and `authorization_context_key` live today in `builtin_plugins/hosted_review/models.py` and move under `mb-s0gv` |
| Provider mirror | `provider_resources/store.py`: `stage_snapshot`, `publish_manifest`, `read_current`, `read_last_complete`, `lease_snapshot`, `reclaim_snapshots` | Publish one repository-scoped, auth-scoped mirror reused by every attachment. The package holds only `profiles.py` today |
| Provider ports | `plugin_api.py`: opaque `GitFetchCredentialLease`, `provider_fetch_authorization_context`, `RepositoryContentPort.open_subject`, `RepositoryObjectJobPort.request_selected_refs`, `ProviderResourceStorePort.stage`, `publish`, `read`, `lease` | Inject narrow cancellable capabilities with typed unavailable, authorization, stale-generation, and publication failures; selected-ref requests carry a non-secret context plus an unforgeable registry handle, never tokens, unrestricted sources, core stores, or paths |

These names are the implementation plan, not registered surfaces.
If implementation finds a smaller boundary that preserves every invariant, the
architecture and beads are updated before code publication.

## Phased Delivery

Phases 1 to 3 are implemented, to the extent the status line above states; the rest are
planned.

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
  The lock order and state machines are
  `tests/fixtures/repository-cache/state-machines.json`.

The thin-mirror plan reversed the choices that served partial clones on 2026-09-23.
Their measurements stay in the exploration as the record to revisit:

- **Blobless acquisition with default-revision prefetch.** Serving the default
  revision’s tree took 5.8–5.9 s blobless against 8.8–17.8 s full for `python/mypy` over
  HTTPS. Stores are full clones now; blobless clones return only if a measurement shows
  full clones too slow for common repositories.
- **Explicit convergence, object-ID requests, and recorded promisor remotes.** No store
  is missing objects, so nothing converges, requests blobs by ID, or has a promisor
  remote. The configuration snapshot that guarded promisor remotes was never verified on
  reads and is gone.
- **No implicit lazy fetch.** `GIT_NO_LAZY_FETCH=1` stays set on every store read as
  defense in depth; no behavior depends on it.
- **Durable refs, coalesced fetch jobs, and job refs.** Nothing prunes a store, so a
  commit stays reachable without a ref of Metabrowser’s own, and refresh is one plain
  fetch under one lock per mirror.

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
- the initial-acquisition stall bound (Phase 1B-a); and
- whether distribution Git builds that backport the security fixes under an older
  version string are admitted (Phase 1B-a).

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
