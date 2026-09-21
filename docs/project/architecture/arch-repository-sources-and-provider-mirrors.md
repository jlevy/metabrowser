# Repository Sources and Provider Mirrors

**Status:** Proposed correction under review; implementation is planned for v0.12.0.

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
  Git objects, Metabrowser-owned refs, tree indexes
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
through another alias, lease, current pointer, or archival pin.

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
generation. Separate Metabrowser processes may browse different subjects from the same
store concurrently. A later multi-subject server would require subject-qualified
addresses and per-request leases; this design does not imply that unsupported routing.

### Source session and content contract

`SourceSession` is the composition root for one active subject.
It owns:

- the `RepositorySubject` and opaque subject generation;
- its `ContentSource` and navigation/index provider;
- a `SourceCapabilities` envelope; and
- the subject, reader, and store leases released when the session closes.

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
- close all readers and leases.

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

The Python plugin SDK gains additive, bounded operations over an opaque `ContentHandle`:
`resolve_content`, `stat_content`, and `read_content_window`. `resolve_path`,
`resolve_directory`, `relativize_path`, and `served_root` remain filesystem-only with
their existing behavior.
Plugin dispatch does not invoke a legacy path hook when the active source lacks
`filesystem_path`; the corresponding view is absent with a capability reason.
If implementation cannot preserve those existing semantics, it bumps
`PLUGIN_SDK_VERSION` and every built-in manifest in the same commit.

The source-boundary phase updates file and raw delivery, tree and rollup assembly,
container resolution, classification, KPress render/export, event routes, and the
binary, structured, agent-log, diff, image, and Markdown built-in hooks.
Built-ins use content handles where they only need bytes and explicitly require a
filesystem path where their behavior genuinely depends on one.
Plugins receive leased, bounded reader ports, never unrestricted `ContentSource` objects
or cache paths.

## Shared Repository Store

One logical repository store owns one worktree-free Git database plus
Metabrowser-controlled refs.
The exact bare versus no-checkout layout and full versus partial-clone policy remain
measurement decisions, but these invariants do not:

- there is no shared index or checked-out branch;
- no view operation runs `checkout`, `switch`, `reset`, or `worktree add`;
- provider-observed refs are fetched into a private namespace and verified against the
  expected full object ID before publication;
- repository content is self-contained for every object Metabrowser promises to serve;
  it does not depend on alternates into a user-owned checkout;
- tree enumeration and blob reads are bounded and cancellation-aware; and
- maintenance and reclamation cannot remove objects held by a live subject lease.

The repository library assigns a stable internal `RepositoryStoreId`. A conservative,
credential-free Git source identity may create the store before provider resolution.
Later provider binding adds a stable `RepositoryRef` alias.
HTTPS, SSH, provider web URLs, and multiple local remotes may then converge on the same
store without changing their own source records.
Conflicting identities fail closed; they are never merged from owner/name text alone.

A source alias is a generation-checked indirection, not part of a store transaction.
Initial acquisition publishes and validates the immutable store first, then atomically
creates the alias as the sole visibility commit.
A crash between those commits leaves an unreachable completed store that startup may
reclaim or quarantine; it never leaves a visible half-entry.
Repointing takes the source-alias lock and uses compare-and-swap.

When stable provider identity proves that independently populated aliases name one
repository, the canonical `RepositoryStoreId` is derived with a domain-separated digest
of provider kind, canonical provider instance, raw stable repository opaque ID, and Git
object format.
It contains no authorization context or credential and requires no mutable
provider-to-store pointer.
Convergence first creates or opens that deterministically named store, prepares a
verified transfer of required objects and Metabrowser refs, and validates object format
and reachability. It then locks the aliases and affected stores in ascending
`RepositoryStoreId` order, installs the transfer, and compare-and-swap repoints the
aliases. No provider record changes in this transaction: provider snapshots name the
stable `RepositoryRef` and exact object IDs, and resolve the derived store only when a
content lease is requested.
The old store remains until no alias, durable ref, or live lease reaches it.
Failed validation leaves every alias unchanged; unique cached objects are never
discarded.

An attached local checkout does not require an eager second clone.
Hosted metadata can be enabled with only a provider attachment.
The shared repository store is created or hydrated lazily when an immutable branch,
revision, diff, or hosted comparison needs Git objects.
Selected-ref fetches acquire only the declared refs and objects allowed by the measured
fetch policy.

### Read path and performance

The revision source resolves a root tree once and caches its immutable directory index
by tree object ID. Blob access uses a bounded pool of long-lived batch Git readers
rather than spawning one process per file.
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

### Fetch jobs, authorization, and credentials

`FetchAuthorizationContext` is a closed, non-secret job identity with `AnonymousPublic`,
`ProviderPrincipal`, `DeclaredExternal`, and `UnverifiableEphemeral` variants.
`ProviderPrincipal` carries provider kind, provider instance, stable opaque principal
ID, optional visibility-partition digest, and the derived authorization-context key;
`DeclaredExternal` carries an operator-configured context key; and an SSH or
credential-helper source whose principal cannot be proven receives a fresh in-memory
`UnverifiableEphemeral` nonce and never coalesces with another request.
Only the variant and a non-secret key digest enter staged diagnostics; credentials never
enter records or ref names.

`RepositoryObjectJobPort` is the single provider-to-job conversion boundary.
It accepts `AuthorizationContextRef`, validates its mode and field combination, derives
the canonical authorization-context key itself, and maps `anonymous` to
`AnonymousPublic` or `authenticated` to `ProviderPrincipal` with every field above
copied exactly. The key is never accepted from a caller.
An invalid combination fails before job lookup, so the key and visibility partition
participate in job coalescing even when provider instance, principal, source, and
refspec otherwise match.
Phase 2B moves `AuthorizationContextRef` and its key function from the hosted-review
plugin into the neutral `provider_resources` package before this port consumes them, so
core neither imports a domain plugin nor keeps a second key implementation.

Authorization identity and credential execution are separate capabilities.
An authenticated provider-selected fetch also presents a `GitFetchCredentialLease`. The
lease is only an unforgeable, process-local, non-serializable handle into the core-owned
`GitFetchCredentialLeaseRegistry`; the handle object carries no authority of its own.
The trusted credential broker registers each issuance with its provider kind, provider
instance, stable principal, authorization-context key, optional visibility partition,
expiry, cancellation generation, and allowlisted credential-free HTTPS Git sources.
A lease authorizes an authorization-context key, not a broker session: a deferred fetch
may use a lease from a later session whose pinned principal derives an equal key.
A session keeps its registrations live until every Git run using them finishes, then
revokes them. `validate_git_fetch_credential_lease` looks the handle up by identity and
reads every bound value, the expiry, the revocation state, and the cancellation
generation from that registry entry, never from the handle.
No token bytes reach the plugin or the application process.

Every request validates its own context and lease before job lookup, including a request
that would join in-flight work.
An absent, unregistered, expired, revoked, host-mismatched, or source-mismatched lease,
or one whose provider, principal, authorization-context key, or visibility partition
differs from the request context, fails with typed `git_credentials_unavailable` or
`authorization_unavailable`. A provider-principal Git run uses the lease of the request
that started it; a joining request attaches only with its own valid lease for the same
context. When the starting request cancels or its lease is revoked while other requests
remain attached, core terminates that Git run and restarts it once under another
attached live lease for an equal authorization-context key or, when none remains, fails
the remaining requests with a typed error.
Provider-principal work never falls back to ambient Git credentials, SSH agents, or
another `gh` login. Phase 2B defines the registry protocol and proves it with a test
issuer.
Until the Phase 3A askpass projection exists, a provider-principal request with a
valid lease still fails with `git_credentials_unavailable` before Git starts.

`git/process.py` remains the only Git subprocess boundary.
Phase 3A projects a validated lease through a packaged askpass bridge to the broker,
with no token in argv, the child environment, a file, a ref, a record, or diagnostics.
Git reads credentials from more places than its own environment variables, so a
provider-principal run is isolated from each of them:

- **Environment.** The run receives a short allowlisted environment rather than a
  scrubbed copy of the parent’s: a fixed `PATH` and locale, an empty Metabrowser-owned
  `HOME` and `XDG_CONFIG_HOME`, terminal prompting disabled, and only named proxy and
  certificate variables.
  `NETRC`, `SSH_AUTH_SOCK`, inherited `GIT_CONFIG_*` values, `GIT_TRACE*`,
  `GIT_CURL_VERBOSE`, and `GIT_SSL_NO_VERIFY` never pass, so a `.netrc` login, an SSH
  agent, injected configuration, or a curl trace cannot supply or print a credential.
  Among Git configuration variables the runner sets only `GIT_CONFIG_NOSYSTEM=1`; it
  also passes platform-required variables it names, such as `SYSTEMROOT` on Windows.
- **Configuration.** System and global Git configuration are disabled.
  The fetch runs in a temporary repository created with an empty template, whose only
  configuration is what Metabrowser writes; it may use the store’s object directory as
  an alternate for negotiation.
  Git then reads the store’s Metabrowser-written configuration only in a local
  ref-listing child with no network access, which is one reason stores use an empty
  template and never accept user configuration.
  It never fetches inside the shared store or a quarantine that reads the store’s
  configuration, and repository stores are also created with an empty template.
  The run uses an empty credential-helper list, disables hooks, and allows only the
  HTTPS protocol, so no helper supplies, stores, or erases the credential and no
  `url.*.insteadOf` rewrite or `http.*.extraHeader` changes the transport or principal.
- **Prompt binding.** The run disables HTTP redirects and sets `credential.useHttpPath`
  and a fixed credential username, so Git asks exactly one password question that names
  the full source URL. Immediately before spawning Git, core arms exactly one answer at
  the broker that registered the run’s lease, for that run, lease, and source URL, and
  disarms it when Git exits, the run is cancelled or restarted, or the lease is revoked;
  the broker answers nothing that is not armed.
  It compares the prompted URL after removing the fixed username and applying Git’s
  credential URL form, a percent-decoded path without a trailing slash, and it registers
  allowlisted sources only in that form.
  A redirect fails with a typed error instead of carrying the credential to another
  host.

Phase 3A measures and chooses the cross-platform inherited-pipe or local-IPC bridge
mechanism, but it may not weaken these boundaries.
Public anonymous jobs and explicitly declared external Git jobs retain their separate
credential policies.

Fetch jobs are keyed by repository store, source identity, `FetchAuthorizationContext`,
fetch-policy version, and exact requested refspec.
They receive an explicit credential-free source URL and do not treat shared `origin`
configuration as authority.
Private ref namespaces include the source and request identities, so an SSH failure or
cancellation cannot poison an HTTPS request for the same store.
Clients in one process join compatible in-flight work instead of starting duplicate
fetches.
Across processes, staged jobs may overlap; each records the store generation and
expected remote object IDs it observed.
Network acquisition uses an isolated temporary repository or, for jobs without provider
credentials, a Git quarantine, and writes a `StagedFetch` record containing the source
and authorization policy, exact refspec, expected OID, object format, and base store
generation. For a pull request, base, head, and optional merge objects each name a
provider-declared credential-free HTTPS acquisition source: the repository that holds
the object, or the base repository’s `refs/pull/<n>/head` and `refs/pull/<n>/merge`
refs, which remain fetchable after a fork is deleted.
Every declared source belongs to the allowlist of a lease whose authorization-context
key equals that of the observation that recorded the object IDs.
Acquisition never inherits an attached checkout’s remote or credential helper.
Publication briefly takes the repository-store lock, validates and imports staged
objects, verifies the expected OIDs, and uses generation-checked compare-and-swap to
advance only Metabrowser-owned refs.
A slower job whose observation would regress a ref or replace a newer generation loses
publication and discards its staged result or retries from the new generation.
Readers already pinned to an object ID continue unaffected.

### Git path and blob semantics

`GitPath` is an immutable tuple of raw non-NUL byte segments with bytewise equality and
stable byte ordering.
It is never converted to a host `Path`. The wire codec encodes each segment as `g1-`
plus unpadded base64url; envelopes carry a separate replacement-safe display string.
Tree routes, file routes, diff entries, review anchors, and provider URL reductions use
the same identity. Parent and child operations manipulate segments, not slash-joined
native strings.

Tree enumeration uses NUL-framed Git output.
Symlinks are entries whose blob bytes name the link target and are never followed.
Gitlinks are distinct non-folder entries that carry the referenced commit OID. Git LFS
pointer files remain ordinary blobs; no smudge filter or implicit LFS network request
runs.

Each long-lived `cat-file --batch-command` process is owned by one actor and serves one
exclusive request at a time.
It issues `info` before `contents`, rejects a blob whose declared size exceeds the
measured preview or raw limit, and drains the complete frame.
Cancellation, timeout, unexpected framing, or a short body poisons and restarts the
process. Only validated full OIDs enter the line protocol; byte paths are resolved
separately through NUL-framed tree lookup.
Promisor misses are reported as `object_unavailable` with implicit lazy fetch disabled;
the object-job port owns any subsequent network request.

A valid repository subject opens without network access.
Git refs and objects refresh only for an explicit refresh or when a requested ref or
object is absent, which is a typed content miss rather than a cache-hit refresh.
Provider observations have a separate stale-while-revalidate policy: invoking an enabled
hosted capability reads the current valid snapshot immediately and may schedule one
coalesced refresh when its declared profile is stale.
An explicit offline mode suppresses that refresh, and deterministic cache-hit tests use
offline mode. Failure leaves prior validated refs, subjects, and provider snapshots
available with honest stale or offline state.

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

## Locks, Leases, and Reclamation

The fixed lock order is:

1. application-home lock for layout migration and global enumeration;
2. source-alias lock for alias creation or compare-and-swap repointing;
3. one or more repository-store locks in ascending `RepositoryStoreId` order for ref
   publication, Git maintenance, object transfer, and object reclamation; and
4. provider-resource lock for binding, snapshot publication, pointer movement, and
   provider reclamation.

Network and long-running Git processes hold none of these locks.
Publication reacquires only the required locks, in order, and revalidates its generation
and authorization context.
Repository refs and provider `current` and `last-complete` pointers use compare-and-swap
publication against the generation observed before staging; stale jobs cannot move a
pointer backward or replace a newer observation.
A local checkout is never a lock target.

Each store is published with a maintenance lock file.
A live subject holds a shared OS lock on that file; Git maintenance, pruning, and store
reclamation require its exclusive lock.
Process exit releases the shared lock, including after a crash.
Durable private refs separately keep every object promised for offline reuse reachable
to Git when no process is running.
Provider snapshot readers similarly hold a shared lock on the published generation while
reclamation takes the exclusive lock before moving it to trash.
Lock files exist before publication so a read-only cache hit opens them without creating
state. Windows reclamation moves only after exclusive acquisition and never depends on
unlinking an open file.

Reclamation preserves objects reachable from live subjects, durable provider-selected
refs, current and last-complete pointers, bounded diagnostics, and archival pins.
Removing one attachment or source alias cannot reclaim state still reachable through
another consumer.

## Implementation Seams

The first implementation phases use these file- and function-level boundaries:

| Area | Files and functions | Responsibility |
| --- | --- | --- |
| Subject and Git target | `repository_context.py`: `RepositorySubject`, `AttachedFilesystemSubject`, `GitRevisionSubject`; `git/process.py`: `GitCommandTarget`, `run_git`, `spawn_git_process`, askpass bridge | Separate session selection from a filesystem path, allow every Git reader to target a trusted worktree or worktree-free repository without environment injection, and project validated broker credentials into provider-selected Git fetches under environment, configuration, and prompt-binding isolation without exposing them |
| Content source | `content_source.py`: `SourceSession`, `SourceCapabilities`, `ContentSource`, `ContentHandle`, `ContentEntry`, `read_window`, `list_directory`; `inventory_engine/coordinator.py`: source-session lifecycle | Preserve the filesystem provider while adding capability-aware content sessions without fake filesystem metadata |
| Plugin and route bridge | `plugin_api.py`: `resolve_content`, `stat_content`, `read_content_window`, filesystem-only path helpers; `server.py`, `view_routes.py`, `sse.py`, `tree.py`, `plugin_loader/classify.py`, built-in sidekicks | Move byte consumers to content handles, capability-gate filesystem-only behavior, and keep route, CLI, and golden parity |
| Revision tree | `git/tree_source.py`: `GitPath`, `GitTreeSource`, `resolve_tree`, `list_tree`, `read_blob`; `git/process.py`: actor-owned batched object reader lifecycle | Serve full-OID trees and blobs with bounded, byte-safe, reusable Git processes and no materialization |
| Repository store | `cache/repository_store.py`: `resolve_store`, `stage_fetch`, `publish_refs`, `lease_revision`, `converge_store`, `reclaim_objects`; `cache/records.py`: `StagedFetch`, source aliases, and store state | Own the worktree-free Git database, isolate staged fetches, converge proven aliases, publish by generation, and retain leased objects |
| Source attachments | `provider_resources/models.py`: source binding and local-availability records; `repository_context.py`: remote candidate discovery | Map local and managed sources to stable provider repository identity without storing local paths or requiring a cache entry |
| Provider mirror | `provider_resources/store.py`: `stage_snapshot`, `publish_manifest`, `read_current`, `read_last_complete`, `lease_snapshot`, `reclaim_snapshots` | Publish one repository-scoped, auth-scoped mirror reused by every attachment |
| Provider ports | `provider_resources/models.py`: `AuthorizationContextRef`, `authorization_context_key`; `plugin_api.py`: opaque `GitFetchCredentialLease`, `provider_fetch_authorization_context`, `RepositoryContentPort.open_subject`, `RepositoryObjectJobPort.request_selected_refs`, `ProviderResourceStorePort.stage`, `publish`, `read`, `lease`; `cache/jobs.py`: `GitFetchCredentialLeaseRegistry`, `validate_git_fetch_credential_lease`; `provider_process.py`: `issue_git_fetch_credential_lease` | Inject narrow cancellable capabilities with typed unavailable, authorization, stale-generation, and publication failures; selected-ref requests carry a non-secret context plus an unforgeable registry handle, never tokens, unrestricted sources, core stores, or paths |
| File and raw routes | `view_routes.py`, `server.py`, `plugin_api.py` | Resolve the active content-source handle rather than assuming the global root is a `Path`; retain route, CLI, and golden parity |

These names are the implementation plan, not registered surfaces.
If implementation finds a smaller boundary that preserves every invariant, the
architecture and beads are updated before code publication.

## Phased Delivery

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
- a dirty attached checkout remains byte-for-byte unchanged while provider data and
  selected refs refresh;
- two local clones plus HTTPS and SSH URL opens for one stable provider repository share
  one provider mirror and converge on one repository store;
- provider records can be cached and refreshed for an attached checkout before a managed
  repository store exists;
- a force-push race cannot publish a provider/Git combination with mismatched object
  IDs;
- two processes racing to refresh one ref or provider resource cannot let a slower,
  stale job regress a ref or pointer after a newer generation publishes;
- authorization contexts never share pointers, validators, deletion evidence, or
  freshness merely because object bytes deduplicate;
- provider kind and visibility-partition differences map to distinct `ProviderPrincipal`
  job keys, and a malformed or mismatched `AuthorizationContextRef` is rejected before
  coalescing;
- an authenticated provider observation and its selected Git fetch use the same stable
  principal even when ambient Git credentials name another account, and a missing,
  unregistered, expired, revoked, or mismatched lease fails closed without an ambient
  fallback, including for a request that joins in-flight work;
- a handle object that claims one principal but is registered for another authorization
  context, or is not registered at all, is rejected by the registry lookup, and a
  deferred fetch succeeds with a later session’s lease for an equal key;
- a token-only private-provider fixture can fetch selected objects with ambient Git
  authentication disabled, while argv, environment, diagnostics, files, records, ref
  names, and cancellation output remain secret-free even with `GIT_TRACE_CURL` set in
  the parent, proved against a local HTTPS fixture whose test certificate authority
  arrives through an allowed certificate variable;
- a conflicting `.netrc` login, SSH agent, credential helper, SSH `insteadOf` rewrite,
  and extra authorization header in system, global, environment-injected, template, or
  repository-local configuration are neither consulted nor written by a
  provider-principal fetch;
- an HTTP redirect to another host fails with a typed error and never receives the
  credential, and the broker answers only an armed run’s normalized source URL, never a
  request from a cancelled, restarted, or revoked run;
- fork PR base, head, and merge objects use their provider-declared HTTPS sources,
  including base-repository pull refs after a fork is deleted, under leases for the
  observation’s authorization-context key, with broker crash, revocation, and
  cancellation reaping Git and its askpass bridge;
- a valid cached view opens while another client refreshes, and failed refresh leaves
  the prior validated observation available;
- purging or detaching one consumer does not remove objects or snapshots leased or
  reachable by another; and
- a crash releases live OS leases, while durable refs keep promised offline objects
  reachable; GC, repack, provider reclamation, and Windows trash movement wait for the
  exclusive maintenance lock;
- cancellation mid-blob, an oversized blob, a promisor miss, invalid UTF-8, a newline in
  a Git name, a symlink, and a gitlink all produce the specified bounded result without
  desynchronizing another reader; and
- every new route, model, persisted state, and browser interaction has `metab` parity,
  exact goldens, and an architecture-map entry when it becomes registered.

## Open Measurement Decisions

Phase 0 measurements choose, and record beside the resulting constants:

- bare repository versus another worktree-free Git layout;
- full clone versus partial-clone filters and explicit bulk prefetch thresholds;
- batch reader pool size, tree-index bounds, and cancellation latency;
- refresh age, process-local request coalescing, and cross-process retry and contention
  bounds; and
- retention and maintenance thresholds for repository objects and provider artifacts.

These choices may tune cost.
They may not introduce shared working-tree state, make a local checkout cache authority,
or weaken immutable and authorization-scoped publication.

## References

- [git-cat-file](https://git-scm.com/docs/git-cat-file) documents the batch object-read
  protocol used by immutable revision sources.
- [git-ls-tree](https://git-scm.com/docs/git-ls-tree) documents tree enumeration without
  a checkout.
- [Partial clone](https://git-scm.com/docs/partial-clone) defines the
  object-availability model evaluated before choosing any filtered acquisition policy.
- [git-maintenance](https://git-scm.com/docs/git-maintenance) documents repository
  maintenance whose scheduling must honor subject leases and store locks.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
