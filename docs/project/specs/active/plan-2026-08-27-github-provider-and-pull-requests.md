# Feature: Hosted Review Model and GitHub Provider

**Date:** 2026-08-27 (refreshed 2026-09-14)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Ready for the v0.11.0 pull-request slice

## Vision

Once a repository is in the local cache, Git already answers most questions about it:
history, revisions, diffs, and file content all work through the shipped pipeline.
What Git cannot answer is what happened *around* the code — the pull request that
proposed a change, the review that argued about it, the checks that gated it.

This plan adds that layer, and only that layer.
GitHub is the first provider adapter, not the durable domain model.
The adapter normalizes GitHub into strict provider-neutral hosted-review records, stores
them as immutable snapshots beside the cached repository, and renders them through
plugin views that resolve code content back to Git object IDs.

Git stays authoritative for content, history, and diffs.
Provider records describe hosted state and *refer to* immutable Git object ids; they
never replace the object database.
A pull or merge request is a hosted-review document that references a Git comparison.
Its patch reuses File Diff Format, its base and head reuse revision content, and its
title, description, lifecycle, reviews, threads, checks, merge state, and freshness stay
available through the richer hosted-review format.
A future GitLab adapter (`mb-51uj`) is a named consumer of the same boundary, but this
release adds only GitHub behavior and only fields proven by that implementation.

## Why this is a separate plan

This work was Phases 4 through 7 of the
[repository-library plan](plan-2026-08-11-open-repo-from-git-url.md).
It moved here because the two have diverged in every dimension that matters for
planning:

- **Different dependencies.** Generic acquisition is gated on the Git-status clean
  predicate, and serving any fetched content is gated on the content-trust chain.
  Provider modeling can start independently; provider acquisition needs only a published
  cache entry plus the narrow job and selected-ref foundation in `mb-jlon`.
- **Different risk.** The cache is filesystem and format work whose failure modes are
  local and recoverable.
  This is network, authentication, rate-limit, and pagination work whose failure modes
  are partial and remote.
- **Different priority.** They are now scheduled independently, and a single document
  meant the generic cache contract was re-reviewed every time the provider model moved.

The repository-library plan keeps the generic phases: format foundation, acquisition and
URL opening, catalog and refresh, the chooser, and large-repository support.

## v0.11.0 Milestone

The v0.11.0 milestone is one PR-first vertical slice:

- bind a cached GitHub repository and publish its repository summary;
- cache a bounded, paginated pull-request index with explicit completeness and
  freshness;
- hydrate an immutable bundle for a selected pull request and fetch only that PR’s Git
  refs through core;
- open a repository or `/pull/<number>` GitHub URL directly, including a PR that is not
  present in the cached index; and
- render repository and PR views offline through the existing Git, revision-content, and
  File Diff Format paths.

The index is a discovery cache, not a prerequisite for direct addressing.
Opening a direct PR URL fetches that one PR and updates or supplements the index without
requiring an unbounded repository crawl.
Issue and timeline records and views move to `mb-9rrc`; stacked-PR projections remain in
`mb-glxc`. Both stay in this plan as later phases so the release boundary does not erase
the larger content-model design.

The long-lived layer boundaries, format profiles, plugin ownership, activity projection,
and virtual navigation containers are specified in
[Hosted Review Model and Provider Boundary](../../architecture/arch-hosted-review-model.md).

## What this plan needs from the cache

Named precisely, because the dependency was previously stated as “Phase 2 job/storage
primitives”, which is broader than what is actually required.

| Needed | Why | Where it lives |
| --- | --- | --- |
| A published cache entry with a stable identity | Provider records hang off a repository that already exists locally | Repository library Phase 1B |
| Atomic publication and no-replace rename | Snapshot sets and manifests need the same publication guarantee the cache uses | Repository library Phase 1A |
| Application-home locking | Provider refresh must not race generic refresh on one entry | Repository library Phase 1A |
| Job progress, cancellation, and stage outcomes | A provider refresh is a long multi-stage operation that must report per-stage results | Repository library extraction `mb-jlon` |
| Core Git ref fetching on request | Pull-request heads live in refs the plugin asks core to fetch; the plugin never runs Git | Repository library extraction `mb-jlon` |

The catalog, chooser, purge, and size accounting in `mb-0ybg` are **not** prerequisites.
The job lifecycle and selected-ref fetching have therefore been extracted into
`mb-jlon`, which can land before the full generic management phase.

## Provider-Neutral Hosted Review Model v1

The model covers the read-only hosted-review domain, not every product surface a code
host exposes. Administrative APIs and unrelated project-management objects do not
contribute to browsing source or reviewing a change.
Claiming to model all of them would leave the phase with no completion criterion.

Phase 0 models the repository and change-request subset before Phase 3 performs an API
request. It lands Pydantic models, compiled SoftSchema contracts, field documentation,
normalized fixtures, invalid fixtures, relationship tests, and a format inventory.
No renderer reads a provider record that the inventory does not register.
The issue, timeline, and stack families extend the same closed registry in later phases;
they do not block the PR-first model from becoming usable.

### The corpus needs a coverage oracle, not just fixtures

Writing the model before the adapter is the right order, and the reason is in the
[design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md):
if the first fixture corpus comes from one API query, that response shape becomes the
model. Hand-authored normalized fixtures avoid that.

They also cannot answer a different question.
A fixture proves the model is self-consistent and that validation rejects what it
should. It cannot prove that GitHub actually supplies a modeled field, or supplies it
over the transport Phase 3 uses.
Nothing in a hand-written corpus fails when a field turns out to be unobtainable, so the
discovery lands in Phase 3, after the initial contracts and their fixtures are frozen.

Phase 0 therefore validates its inventory against a small set of **recorded, scrubbed**
real responses, used only as a coverage oracle:

- captured once, from public repositories, with tokens, rate-limit headers, and volatile
  transport metadata removed;
- kept outside the fixture corpus and never loaded by a renderer, an adapter, or a
  contract test — it is not authoritative and does not become a second model; and
- consumed by exactly one check, which asserts that every field in the contract
  inventory is present in at least one recorded response, and reports the transport that
  supplied it.

A field that no recorded response supplies is not automatically wrong — it may be
derived, or intentionally Metabrowser-owned like `ChangeRequestStack/v1`. It just has to
be labeled as such deliberately rather than by omission.

This keeps the review’s ordering (the model leads) while removing its blind spot (the
model is unfalsifiable until Phase 3).

### One provider port, one v0.11.0 transport

The hosted-review port is provider-neutral; its first implementation is
`GitHubGhAdapter`, backed by the installed `gh` CLI and explicit `gh api` requests.
This keeps authentication, active-account selection, GitHub Enterprise host handling,
REST, and GraphQL behind GitHub’s supported client while Metabrowser owns bounds,
normalization, immutable snapshots, and errors.

The adapter does not run `gh pr view` as a second presentation model.
It uses explicit REST endpoints or GraphQL queries through `gh api`, maps each response
immediately into the hosted-review contracts, and discards the raw response.
GraphQL is expected for review decisions and aggregate review state that REST does not
provide; each modeled field names its acquisition source in the coverage oracle without
exposing that transport in the durable domain record.

The adapter invokes one page at a time and never uses `gh api --paginate`, because the
application’s own item, page, byte, time, and cancellation limits must stop the walk.
It also avoids `gh api --cache`; Metabrowser’s validated provider store is the cache of
record, and an opaque transport cache would create a second freshness authority.

Authentication is a typed preflight and recovery path:

- `gh auth status --active --hostname <host> --json hosts` diagnoses the selected host
  without `--show-token`; the adapter parses the JSON status because `gh` documents JSON
  mode as exiting successfully even when an account has an authentication problem;
- `gh api --hostname <host>` performs requests and obtains credentials from `gh` or its
  supported token environment without returning a token to Metabrowser;
- missing CLI, missing login, insufficient scope, permission loss, rate limiting, and
  network failure remain distinct provider states; and
- a request path never starts interactive login.
  The UI gives the user a copyable `gh auth login --hostname <host>` recovery command
  and retries only after an explicit action.

Every `gh` process uses a no-shell, bounded, cancellable runner with capped stdout and
stderr and a sanitized environment.
Secrets, auth output, request headers, and raw error bodies never enter logs or cache
records.
A later direct-HTTP GitHub adapter or GitLab adapter may implement the same port
if measurement or deployment needs justify it; neither changes the common format or
views.

### Record families

| Family | Contracts | Purpose |
| --- | --- | --- |
| Provider storage | `ProviderBinding/v1`, `Retrieval/v1`, `ProviderSyncManifest/v1`, `ResourceSet/v1`, `Tombstone/v1` | Bind the generic entry to a stable hosted repository, describe acquisition, and publish complete snapshot sets |
| Repository | `HostedRepository/v1` | Stable provider identity, owner/name, URLs, visibility, default branch, and provider timestamps |
| Work items (later, `mb-9rrc`) | `Issue/v1`, `IssueComment/v1`, `TimelineEvent/v1` | Issues and their bounded discussion and state history |
| Change requests | `ChangeRequestIndex/v1`, `ChangeRequest/v1`, `Review/v1`, `ReviewThread/v1`, `ReviewComment/v1` | Bounded discovery summaries plus selected pull- or merge-request state, Git endpoints, decisions, threads, and line anchors |
| Commit signals | `Check/v1`, `CommitStatus/v1` | Mutable provider conclusions attached to an immutable commit ID |
| Activity projection | `RepositoryActivity/v1` | A bounded, source-neutral page of commit or change-request references for history-style navigation |
| Derived relationships (later, `mb-glxc`) | `ChangeRequestStack/v1` | Explicit, provenance-bearing dependency edges and display order; never presented as a provider-native object |

The first mapping matrix is reviewed as part of the format, not left implicit in adapter
code:

| GitHub concept | Hosted-review projection | Boundary |
| --- | --- | --- |
| Repository node and `nameWithOwner` | `HostedRepository/v1` and `ProviderObjectRef` | Provider coordinates remain provenance; stable opaque identity is authoritative |
| Pull request | `ChangeRequest/v1` | `provider_ref.object_kind: pull_request`; a future GitLab merge request uses the same common record with another provider kind |
| Base, head, and merge commit | `RevisionRef` and `ComparisonRef` | Full Git object IDs; availability is explicit and content stays in Git |
| Draft, open, closed, merged, locked | Common lifecycle and capability fields | Unknown provider values normalize to `unknown`, never to a guessed state |
| Review decision and requested reviewers | Change-request review summary | Aggregate state is distinct from the bounded review collection |
| Review, review thread, review comment | `Review/v1`, `ReviewThread/v1`, `ReviewComment/v1` | Anchors preserve provider and immutable comparison identity; mapping failure stays unresolved |
| Check suite, check run, commit status | `Check/v1`, `CommitStatus/v1` | Attached to immutable revision IDs; provider-only details use a declared companion record |
| Labels, assignees, milestone | Common bounded references | Only values consumed by discovery or detail views enter v0.11.0 |
| Provider timestamps and API observations | Object timestamps plus `Retrieval/v1` | Hosted state and retrieval freshness never share one timestamp |

SoftSchema maturity follows the evidence:

1. Hand-authored and scrubbed GitHub examples begin as named `soft` or `permissive`
   artifacts while field meaning and consumers are reviewed.
2. Pydantic models compile deterministic schemas; Python and browser consumers validate
   the same corpus and semantic invariants.
3. Before Phase 3 publishes durable cache entries, every released contract is
   `enforced`, the host registry binds its packaged schema, and undeclared fields fail.

The progression lets the schema develop without making cached data vague.
Nothing written into a released provider cache remains permissive.

Small values such as `ActorRef`, `RepositoryRef`, `Label`, `MilestoneRef`,
`GitObjectRef`, and `CollectionState` are nested `$defs`, not independently refreshed
files. An actor reference carries enough identity and display information to render when
no full actor resource was fetched.

Issue and change-request records are separate closed contracts.
A GitHub pull request is not also written as an issue record, so common provider fields
do not acquire two authorities.
Shared code may project either type into an in-memory work-item summary.
It does not use an open union or an untyped `data` mapping on disk.

### Identity and Git references

Every provider object stores a `ProviderObjectRef`: provider kind, provider instance,
object kind, stable opaque provider ID, repository ID, human URL, and repository-local
number where applicable.
File paths use a safe digest or encoded resource key; the full provider ID inside the
record is authoritative.
Repository renames change display coordinates, not provider identity or generic cache
identity.

Change requests record:

- stable change-request and repository IDs, provider-native kind, number, URL, title,
  author, normalized state, draft/locked flags, provider timestamps, labels, assignees,
  milestone, and review decision;
- base and head repository IDs, ref names, and full Git object IDs;
- an optional merge object ID and its observation state;
- requested reviewers and teams as bounded references; and
- provider-reported aggregate counts where GitHub exposes them without fetching a
  collection.

The proposed `frontmatter-md` artifact is concrete enough to fixture before acquisition
work:

```markdown
---
softschema:
  contract: com.github.jlevy.metabrowser.review:ChangeRequest/v1
  envelope: change_request
  status: enforced
change_request:
  id: github:github.com:R_kgDOExample:pull:123
  provider_ref:
    provider: github
    instance: github.com
    object_kind: pull_request
    opaque_id: PR_kwDOExample
  repository:
    provider: github
    instance: github.com
    opaque_id: R_kgDOExample
  number: 123
  url: https://github.com/example/project/pull/123
  title: Add repository caching
  author:
    provider_ref: U_kgDOExample
    handle: octocat
    url: https://github.com/octocat
  state: open
  draft: false
  locked: false
  created_at: "2026-08-20T12:00:00Z"
  updated_at: "2026-08-26T15:30:00Z"
  closed_at: null
  merged_at: null
  base:
    repository_id: R_kgDOExample
    ref: main
    oid: 0123456789abcdef0123456789abcdef01234567
    availability: present
  head:
    repository_id: R_kgDOFork
    ref: cache-design
    oid: 89abcdef0123456789abcdef0123456789abcdef
    availability: present
  merge_commit: null
  labels: []
  assignees: []
  milestone: null
  review:
    decision: required
    requested_people: []
    requested_teams: []
  counts:
    commits: 4
    discussion_comments: 2
    reviews: 1
---
This pull request adds a versioned repository cache and makes repeated URL opens reuse
the validated local entry.
```

YAML is authoritative for every value software consumes.
The Markdown body is the provider’s PR description, preserved as reader-facing content;
no route, index, or view parses it to recover fields.
That lets the existing Markdown renderer present the description under the untrusted
profile while the hosted-review plugin composes the structured header, reviews, checks,
threads, and diff around it.
`ChangeRequestIndex/v1`, manifests, retrieval records, and compact companion objects use
`pure-yaml` because their whole payload is structured.

Phase 0 freezes the exact field set, artifact profiles, and enum policy from
representative fixtures.
It may split a field into another typed record, but it cannot replace a modeled field
with an opaque provider payload.

Content and diffs are read from Git by object ID. Provider commits and files are fetched
only when they carry provider-only annotations or prove collection completeness.
Review anchors store path, side, line or range, original commit ID, current commit ID
when available, and an explicit outdated/unresolved state.
The UI never invents a current line when an anchor cannot be mapped.

### Completeness, freshness, and absence

Every collection entry in a resource-set or sync manifest reports one of
`not_requested`, `partial`, `complete`, or `unavailable`, plus bounded pagination
information. A missing comments list is therefore not silently interpreted as “no
comments.”
Truncation records its reason, limit, and next cursor or page when one exists.

Provider `created_at` and `updated_at` describe the hosted object.
Retrieval time, transport, API version, query identity, HTTP validators, rate-limit
observation, and normalization version belong to retrieval metadata.
This prevents a conditional HTTP detail from becoming part of the domain object’s
identity.

`ChangeRequestIndex/v1` is a bounded discovery projection, not a bag of complete PR
records. Each row contains only stable identity, number, URL, title, state, draft state,
author, base/head labels, and provider timestamps needed to choose a PR. The index
records its requested state filter and sort, page cursors, item and page bounds,
observed repository revision, retrieval metadata, and collection state.
Changing those query inputs produces a new immutable observation; it does not silently
reinterpret an existing index.
Reviews, threads, checks, descriptions, and Git-ref availability belong to the selected
PR bundle and are never multiplied across list rows.

A confirmed deletion receives a tombstone.
Authentication failure, permission loss, rate limiting, and a resource never fetched are
distinct states. Refresh does not turn any of them into deletion.

### Stacked pull requests

Code hosts do not provide one universal stacked-change-request object.
`ChangeRequestStack/v1` is a Metabrowser projection over change requests and Git
history. It contains:

- the ordered member pull-request IDs;
- directed edges with a controlled relation such as `depends_on`;
- the evidence for each edge, such as base/head topology, explicit user metadata, or a
  named tool adapter;
- derivation algorithm and version;
- observation time and source snapshot IDs; and
- conflicts, cycles, missing members, and confidence where the evidence is not
  definitive.

The model never silently treats numbering, creation time, or adjacent branches as a
dependency. The later stack phase defines and fixtures the record, then implements
derivation and navigation after ordinary PR snapshots and views are stable.

## Provider Snapshot Storage

Provider records are mutable observations, but cache publication should still be atomic
and old data should remain readable during refresh.
The provider directory begins in Phase 3:

```text
<entry>/providers/github/
├── binding.yml
├── objects/
│   └── <kind>/
│       └── <resource-key>/
│           └── <snapshot-id>.<md-or-yml>
├── manifests/
│   └── <sync-id>.yml
└── views/
    ├── repository/current.yml
    ├── pull-requests/index/current.yml
    ├── pull-requests/<number>/current.yml
    └── issues/<number>/current.yml       # later: mb-9rrc
```

An object snapshot is immutable after publication.
Its snapshot ID is derived from its contract ID and canonical normalized payload.
Retrieval time, validators, query identity, and rate-limit state live in the sync
manifest, so a conditional response can reuse an unchanged object instead of writing a
byte-different copy.
A sync manifest names the exact object snapshots, collection states, and failures that
make up one completed acquisition.
Each small `current.yml` is an atomic `ResourceSet/v1` pointer to a completed manifest;
the browser never follows staging files or a half-written multi-page response.

The physical layout remains an implementation hypothesis until Phase 0 fixtures measure
path length, object counts, YAML size, parse time, and snapshot duplication.
The invariants are fixed: immutable snapshots, atomic current manifests, strict
contracts, safe path keys, explicit completeness, and no cross-entry writes.
If measurement favors a sharded or indexed equivalent, the architecture map and layout
format must say so before Phase 3 writes released data.

Raw API responses are not authoritative and are not stored by default.
A future bounded diagnostic capture, if justified, belongs under a separate
content-addressed namespace, removes secrets and volatile headers, and has an explicit
retention policy.

## GitHub Acquisition Boundary

Phase 3 adds a built-in GitHub provider plugin after the model, cache, and URL phases.
It maps REST or GraphQL responses into transport-neutral records; the durable schema
does not expose response shape, pagination syntax, or client-library types.

The provider binding resolves a generic cache entry to a stable GitHub repository ID
without changing the cache source digest.
The v0.11.0 adapter invokes `gh api`; credentials remain in `gh`, its operating-system
credential store, or its supported token environment.
The plugin reports authentication capability and failure state but never asks `gh` to
show a token or reads a secret into a cache record.

Initial acquisition is on demand:

- repository summary for the repository tab;
- a bounded, paginated PR index for repository discovery, carrying explicit freshness,
  page cursors, truncation reason, and `partial` or `complete` collection state; and
- one selected pull-request bundle, including only the bounded collections needed by the
  first PR view.

Listing a PR never fetches its Git refs.
Selecting it does. A direct `/pull/<number>` URL may bypass the index and hydrate only
that PR, so an old, closed, or not-yet-indexed pull request remains addressable.
Issue acquisition is the later `mb-9rrc` expansion.

Bulk mirroring is not required.
Conditional requests, cursor continuation, API budgets, field and collection bounds, and
rate-limit reporting are part of the acquisition contract.
A completed provider refresh atomically publishes a new manifest.
A failed or partial refresh leaves the previous current manifest readable and exposes
the new failure separately.

Selected pull requests may require fetching provider refs into a Metabrowser-owned Git
ref namespace. The plugin asks the core Git cache service to do that work.
It does not run Git itself.
Every base, head, and merge object records whether the object is present, fetchable,
unavailable because a fork disappeared, or outside the configured acquisition bound.

## Retention and Reclamation

The cache plan established that retention without a reclamation rule is how a cache
becomes the largest directory in a home folder, and gave `staging`, `trash`, and
quarantine a rule each.
Immutable provider snapshots need the same treatment, because “immutable” describes a
snapshot’s contents, not its lifetime.

| Held | Retained because | Reclaimed by |
| --- | --- | --- |
| Snapshots referenced by the current manifest | They are the view being served | Never, while that manifest is current |
| Snapshots referenced only by superseded manifests | One prior generation is worth keeping for diagnosis after a bad refresh | Bounded generation count; older manifests and the snapshots only they reference are collectable |
| Snapshots referenced by no retained manifest | Nothing can reach them | Swept with the superseded manifests that orphaned them |
| Everything, for an offline or deleted source | The last validated set may be the only surviving copy | Never automatically; explicit purge only |

The sweep runs under the same application-home lock as generic reclamation, and never
collects a snapshot a live session is serving.
A provider store whose source is gone is the case that must not be swept on a timer — it
is precisely when the cached copy is irreplaceable.

## Security and Trust

Provider content is third-party content, and moving these phases out of the cache plan
must not leave that behind with the phases it applied to.

Every provider string — titles, bodies, comments, review text, actor names — is
untrusted. Markdown and HTML from issues, pull requests, and comments render through the
existing untrusted-content policy, the same one that gates serving a fetched repository
at all.

Provider records are validated before publication and bounded by file, field, and
collection limits established from fixtures and browser measurements, so a hostile or
merely enormous response cannot become an unbounded document or an unbounded render.

Schema selection comes from the installed registry, never from a path inside a cache
file. Provider object ids and URLs never become filesystem paths without safe encoding
and containment checks.
Credentials stay in `gh`, the OS credential store, or an explicit provider adapter; the
plugin reports which source it used and never reads a secret into a record, a log, or a
browser response.

## Phased Implementation Plan

The design boundary lands before network or view work.
After that, implementation follows the user-visible dependency chain rather than
treating “GitHub support” as one feature.

### Phase 0: Hosted Review Format and plugin boundary (`mb-63ym`)

- [ ] Write the provider-neutral contract inventory as Pydantic models and deterministic
  compiled SoftSchema contracts, using simple closed objects and local `$defs`.
- [ ] Use `frontmatter-md` for `ChangeRequest/v1`, with all consumed fields in YAML and
  the provider description as the reader-facing Markdown body; use `pure-yaml` for
  indexes, manifests, and compact companion records.
- [ ] Define stable provider and local IDs, repository refs, Git object refs, provider
  timestamps, retrieval metadata, completeness, pagination, tombstones, unknown enums,
  and explicit provider companion records.
- [ ] Define repository, change request, review, thread, review comment, check, status,
  and activity relationships without an opaque payload or provider-shaped view model.
- [ ] Build normalized and invalid fixtures for open, closed, merged, draft, forked,
  deleted, inaccessible, partial, paginated, direct-addressed, outdated-anchor, and
  unknown-enum cases.
- [ ] Add one GitHub terminology-to-common-model mapping matrix and prove every common
  field has a consumer; do not add speculative GitLab-only fields.
- [ ] Capture the scrubbed response oracle and require every modeled field to be
  observed, derived, or explicitly optional with `not_requested` state.
- [ ] Register the proposed format and plugin surfaces in the architecture map and add
  an inventory check that fails when a contract lacks a producer, consumer, schema, or
  fixture.

### Phase 1: Robust generic repository cache (`mb-ire2` through `mb-dg00`)

This phase is owned by the
[repository-library plan](plan-2026-08-11-open-repo-from-git-url.md), but it is the
first implementation prerequisite here.

- [ ] Publish the versioned application home, strict layout and entry records, locks,
  atomic no-replace promotion, quarantine, trash, and deterministic inspection routes.
- [ ] Acquire one generic Git URL into a pinned, reusable entry through the single
  bounded Git process boundary.
- [ ] Route the cached `gitroot` through the inventory coordinator lifecycle and prove
  offline reuse, interruption recovery, and future-format refusal in goldens.

### Phase 2: GitHub URL opening (`mb-ew38`)

- [ ] Recognize canonical GitHub repository and `/pull/<number>` URLs through a
  provider-neutral URL reducer; reject credentials, ambiguous hosts, queries, and
  fragments the grammar does not own.
- [ ] Resolve or acquire the generic repository entry before invoking a provider
  adapter, and reuse the canonical escaped path-identity codec for every selection.
- [ ] Preserve a directly addressed PR target even when the provider index is absent,
  stale, partial, or does not contain that number.
- [ ] Apply the untrusted-content profile before serving fetched repository or provider
  content.

### Phase 3: GitHub `gh` adapter, binding, and provider cache (`mb-y1ax`, `mb-jlon`, `mb-p4sw`, `mb-duu7`, `mb-wx32`)

- [ ] Define the provider transport port, then implement only `GitHubGhAdapter` with
  bounded `gh api` REST/GraphQL calls and explicit host selection.
- [ ] Route every provider command through the shared no-shell, bounded, cancellable
  subprocess runner (`mb-y1ax`); cap and sanitize stdout, stderr, environment, and
  diagnostics before an adapter sees them.
- [ ] Add non-secret auth preflight and typed recovery states for missing `gh`, missing
  login, insufficient scope, permission loss, rate limiting, network failure, and
  cancellation; never start interactive login on a request path.
- [ ] Add GitHub repository binding without changing generic cache identity.
- [ ] Publish immutable hosted-review snapshots, sync manifests, and atomic current
  pointers; keep the last completed observation readable when refresh fails.
- [ ] Publish a bounded `ChangeRequestIndex/v1` with explicit query, pages, cursors,
  completeness, freshness, and truncation; do not use `gh --paginate`, `gh --cache`, or
  durable raw API responses.
- [ ] Fetch a selected `ChangeRequest/v1` frontmatter artifact and its bounded review,
  thread, check, and status companions, including a direct-addressed PR absent from the
  index.
- [ ] Ask core to fetch only the selected base, head, and optional merge refs into a
  Metabrowser namespace; listing PRs fetches no refs.
- [ ] Add stage-level progress, cancellation, rate-limit observations, and diagnostics
  without turning provider refresh into a generic cache hit.

### Phase 4: Hosted-review views and virtual PR collection (`mb-r19i`, `mb-uh6p`, `mb-rldc`)

- [ ] Register a Pull Requests nav panel backed by the cached index, reusing Git
  history’s bounded paging, virtualization, focus, selection, and restoration patterns.
- [ ] Add the repository-scoped plugin SDK surface (`mb-uh6p`) for virtual nav
  collections, including loading, error, replacement, restoration, and disposal.
- [ ] Model the panel root as a virtual folder-like collection and each PR as an
  item-like document plus a folder-like container whose children are changed files.
- [ ] Render the frontmatter artifact as a PR document: validated title, identity,
  actors, state, merge/review/check summaries, and freshness around the Markdown
  description.
- [ ] Project commit summaries and PR rows through `RepositoryActivity/v1` when sharing
  history UI mechanics; retain separate Git and provider authorities and do not invent a
  mixed global order when pagination cannot support one.
- [ ] Render the selected PR comparison through the existing Git adapter, File Diff
  Format, and diff plugin; render base/head Markdown through revision content.
- [ ] Show reviews, threads, checks, merge state, partiality, offline state, refresh
  status, and unresolved/outdated anchors without adding provider fields to File Diff
  Format.
- [ ] Deliver provider-neutral review threads and diff anchors (`mb-rldc`) with explicit
  outdated, unresolved, and unmappable states.
- [ ] Drive counts and folder visibility from the complete bounded index model, not the
  currently mounted rows.

### Phase 5: Issues and timelines (`mb-9rrc`)

- [ ] Add closed provider-neutral issue, issue-comment, and timeline-event contracts and
  fixtures to the format inventory.
- [ ] Decide whether the primary issue artifact uses `frontmatter-md`, based on the same
  consumed-values/body split as change requests.
- [ ] Acquire bounded issue bundles on direct URL or selection with the same snapshot,
  freshness, partiality, and offline rules as PR bundles.
- [ ] Add issue and timeline views without changing core routes or renderers.

### Phase 6: Stacked change requests and cross-object projections (`mb-glxc`)

- [ ] Implement stack derivation against the common contract with explicit evidence,
  algorithm version, conflicts, and cycles.
- [ ] Add adapter points for explicit stack metadata without hard-coding a third-party
  tool into core or treating heuristics as fact.
- [ ] Add stack navigation, aggregate status, and adjacent comparisons as derived views
  over immutable change-request and Git snapshots.
- [ ] Recompute projections when any input snapshot changes; never mutate source records
  to store derived order.

### Later provider: GitLab (`mb-51uj`)

- [ ] Implement the same provider port for GitLab merge requests, discussions,
  pipelines, auth, pagination, and selected refs after the GitHub-first format and views
  have shipped.
- [ ] Add only fields observed from that adapter and only provider-specific companion
  records with named consumers; do not widen v0.11.0 contracts speculatively.

## Testing Strategy

- **Hosted-review contracts:** every valid frontmatter and pure-YAML fixture passes
  structural and semantic validation in producer and consumer implementations; invalid
  fixtures fail with stable codes and paths; unknown provider enum values normalize
  without opening the record schema; no common contract contains a GitHub-only field.
- **Frontmatter artifacts:** the complete PR description round-trips as the Markdown
  body, structured consumers read only YAML, hostile fences and Markdown remain bounded
  and untrusted, and snapshot identity changes when either authoritative metadata or the
  body changes.
- **Coverage oracle:** every modeled field is present in at least one recorded, scrubbed
  response, or is explicitly marked derived or optional with a `not_requested` state.
- **Provider snapshots:** multi-page and partial refreshes publish only complete
  manifests; a failed refresh leaves the old current set; deletion, permission loss,
  not-requested, and rate-limit outcomes remain distinct.
- **PR index:** configured bounds, pagination cursors, freshness, and completeness are
  visible; list acquisition fetches no PR refs; a direct PR URL works without a warm or
  complete index; raw provider responses never become durable authority.
- **Adapter and auth:** fixtures cover REST and GraphQL mappings, GitHub Enterprise host
  selection, missing CLI/login/scope, permission loss, rate limits, cancellation,
  malformed output, and output bounds without exposing a credential; no test uses an
  interactive login or `gh --paginate`.
- **Relationships:** all references resolve within a manifest or carry an explicit
  unavailable state; stack cycles and missing members are reported, not repaired by
  guessing.
- **Views:** loading, stale, partial, unavailable, and offline states each render
  distinctly; incomplete-collection indicators survive; a review anchor that cannot be
  mapped shows as outdated rather than pointing at an invented line.
- **Navigation:** a cached PR index populates the virtual Pull Requests collection;
  paging and virtualization do not change counts or folder visibility; selecting a row
  opens its hosted-review document; expanding it exposes the same changed-file views as
  any other comparison.
- **Parity:** repository and PR routes, records, persisted pointers, URL reduction, and
  view interaction state each receive an architecture-map row and an exact
  production-path golden.
- **Distribution:** the installed wheel contains every registered model, compiled
  schema, plugin asset, and format inventory.
  `make verify` remains the handoff gate.

## Rollout and Compatibility

Every contract in this plan is unreleased.
There is no legacy provider reader to preserve, and no speculative compatibility layer
is added for one.

Once released, provider cache data is expendable only when it can actually be
reacquired. An offline or deleted source retains its last validated immutable snapshots
until an explicit retention or purge operation removes them.

## References

- [Repository library and open from a Git URL](plan-2026-08-11-open-repo-from-git-url.md)
  — the generic cache this plan builds on
- [Repository-library phasing and GitHub content model](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
  — the design review that produced this model
- [Delivery order for Git status, the repository cache, and providers](../../reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md)
  — the review that separated this plan from the cache
- [Git and comparison sources](../../architecture/arch-git-and-comparison-sources.md) —
  the provider boundary this plan must not cross
- [Hosted Review Model and Provider Boundary](../../architecture/arch-hosted-review-model.md)
  — the durable format, adapter, activity, view, and cache boundaries
- [File Diff Format v1](../../architecture/file-diff-format/file-diff-format.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
