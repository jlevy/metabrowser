# Feature: Hosted Review Model and GitHub Provider

**Date:** 2026-08-27 (refreshed 2026-09-15)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Phase 0C.1 is the green exact stacked base at
`614fef15793ff7cffd0c4e85a577342472fd9686`; Phase 0C.2 is the current implementation
layer for the generic installed format inventory, distribution, and architecture gates

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
A provider resource is published through generic artifact-contract and resource-profile
registries, then selected through a resource-kind and view registry.
That path is reusable for GitHub releases and other external systems; GitHub-specific
URL, acquisition, auth, badges, and actions remain plugin customizations.
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
- open any advertised and authorized branch through the generic repository
  materialization layer;
- hydrate an immutable bundle for a directly addressed pull request and fetch only that
  PR’s Git refs through core;
- then cache a bounded, paginated pull-request index with explicit completeness and
  freshness;
- open a repository or `/pull/<number>` GitHub URL directly, including a PR that is not
  present in the cached index; and
- render repository and PR views offline through the existing Git, revision-content, and
  File Diff Format paths.

The index is a later discovery cache, not a prerequisite for direct addressing.
Opening a direct PR URL fetches that one PR into its independently addressed current
bundle without rewriting an index as though the item matched that index’s query.
The navigation view may surface the selected item beside an existing index, but the
stored index remains an honest observation of its own filter, sort, and bounds.
Issue and timeline records and views move to `mb-9rrc`; stacked-PR projections remain in
`mb-glxc`. Both stay in this plan as later phases so the release boundary does not erase
the larger content-model design.

The long-lived layer boundaries, format profiles, plugin ownership, activity projection,
and virtual navigation containers are specified in
[Hosted Review Model and Provider Boundary](../../architecture/arch-hosted-review-model.md).
The general entity/artifact/resource vocabulary, trusted registries, transparent
Markdown/YAML formats, and external-system mapping workflow are specified in
[External Resources, Artifact Contracts, and Views](../../architecture/arch-external-resources-and-views.md).

The v0.10.0 release gate is closed: the release tag points at the accepted release
commit, and the fetched `main` branch contains it.
The design branch has merged that released `main`, and the first implementation branch
is a formal stack above the design pull request.
Each stacked implementation pull request keeps one independently reviewable phase; it
may be built on the preceding phase before that base lands.
The internal beads are subtasks within that one phase pull request, not separate pull
requests. When a base lands, the next pull request is retargeted or rebased, its exact
phase diff is rechecked, and the full handoff gate runs again before merge.

## What this plan needs from the cache

Named precisely, because the dependency was previously stated as “Phase 2 job/storage
primitives”, which is broader than what is actually required.

| Needed | Why | Where it lives |
| --- | --- | --- |
| A published cache entry with a stable identity | Provider records hang off a repository that already exists locally | Repository library Phase 1B |
| Atomic publication and no-replace rename | Snapshot sets and manifests need the same publication guarantee the cache uses | Repository library Phase 1A |
| Lock hierarchy and entry leases | Provider publication must coordinate with purge, ref mutation, readers, and reclamation without holding a lock across network work | Repository library Phase 1A plus provider-store kernel `mb-i3xc` |
| Owner-only application home | Private repositories and provider records must not be exposed through permissive cache directories | Cache security `mb-xa0p` |
| Job progress, cancellation, and stage outcomes | A provider refresh is a long multi-stage operation that must report per-stage results | Repository library extraction `mb-jlon` |
| Core Git ref fetching on request | Pull-request heads live in refs the plugin asks core to fetch; the plugin never runs Git | Repository library extraction `mb-jlon` |
| Provider capability and lifecycle registry | Hosted-review services must discover, inject, and close adapters without importing GitHub | Provider SDK `mb-ji83` |

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
Every request uses a fixed endpoint template or checked-in GraphQL document with
explicit variables serialized as bounded JSON on standard input through
`gh api --input -`. Raw untrusted values never become path fragments, `-f`/`-F` fields,
headers, or option-like arguments; the few REST path components a fixed template
requires pass a typed allowlist and percent-encoding builder before becoming one
argument.

The runner asks `gh api --include` for response metadata, parses the status line and an
allowlist of rate-limit, validator, request-ID, content-type, and API-version headers,
then parses the bounded body separately.
GraphQL `data` accompanied by `errors`, null nodes, unexpected content types, and output
truncation are typed incomplete or failed outcomes rather than success.
Each GitHub host has an explicit REST API version, `Accept` profile, and checked-in
query identity; an Enterprise host that cannot satisfy them reports
`unsupported_provider_version` instead of silently changing semantics.
Verbose command output is forbidden.

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

Every `gh` process uses a no-shell, bounded, cancellable runner with capped standard
input, stdout, and stderr plus a sanitized environment.
Secrets, auth output, request headers, and raw error bodies never enter logs or cache
records.
A later direct-HTTP GitHub adapter or GitLab adapter may implement the same port
if measurement or deployment needs justify it; neither changes the common format or
views.

### Record families

| Family | Contracts | Purpose |
| --- | --- | --- |
| Provider storage | `ProviderBinding/v1`, `AuthorizationContextRef`, `Retrieval/v1`, `ProviderSyncManifest/v1`, `ResourceSet/v1`, `ProviderViewPointer/v1`, `Tombstone/v1` | Bind the generic entry to a stable hosted repository, describe the non-secret auth context and acquisition, and publish atomic snapshot sets |
| Repository | `HostedRepository/v1` | Stable provider identity, owner/name, URLs, visibility, default branch, and provider timestamps |
| Work items (later, `mb-9rrc`) | `Issue/v1`, `IssueComment/v1`, `TimelineEvent/v1` | Issues and their bounded discussion and state history |
| Change requests | `ChangeRequestIndex/v1`, `ChangeRequest/v1`, `ChangeRequestComment/v1`, `Review/v1`, `ReviewThread/v1`, `ReviewComment/v1` | Bounded discovery summaries plus selected pull- or merge-request state, top-level conversation, Git endpoints, decisions, threads, and anchors |
| Commit signals | `Check/v1`, `CommitStatus/v1` | Mutable provider conclusions attached to an immutable commit ID |
| Activity projection | `RepositoryActivity/v1` | A bounded, source-neutral page of commit or change-request references for history-style navigation |
| Derived relationships (later, `mb-glxc`) | `ChangeRequestStack/v1` | Explicit, provenance-bearing dependency edges and display order; never presented as a provider-native object |
| Releases (later, `mb-7srn`) | `Release/v1`, `ReleaseAsset/v1`, `ReleaseIndex/v1` | Prose-bearing releases, separately mutable asset metadata, and bounded discovery; the provider-storage kernel and view framework are reused without widening PR records |

The first mapping matrix is reviewed as part of the format, not left implicit in adapter
code:

| GitHub concept | Hosted-review projection | Boundary |
| --- | --- | --- |
| Repository node and `nameWithOwner` | `HostedRepository/v1` and `ProviderObjectRef` | Provider coordinates remain provenance; stable opaque identity is authoritative |
| Pull request | `ChangeRequest/v1` | `provider_ref.object_kind: pull_request`; a future GitLab merge request uses the same common record with another provider kind |
| Base, head, and merge commit | `RevisionRef` and `ComparisonRef` | Full Git object IDs; availability is explicit and content stays in Git; a deleted fork may leave head repository identity null while the ref and OID remain |
| Draft, open, closed, merged, locked | Common lifecycle and capability fields | Unknown provider values normalize to `unknown`, never to a guessed state |
| Review decision and requested reviewers | Change-request review summary | Aggregate state is distinct from the bounded review collection |
| Top-level conversation comment | `ChangeRequestComment/v1` | Distinct from a diff discussion; keeps Markdown body and lifecycle but has no review anchor |
| Review, review thread, review comment | `Review/v1`, `ReviewThread/v1`, `ReviewComment/v1` | Review YAML owns identity, nullable author, disposition, lifecycle, timestamps, and relationships while an optional Markdown body owns summary prose; anchors preserve provider and immutable comparison identity; an unavailable original commit stays observed rather than becoming `not_requested`; file-level, line, and range forms remain distinct; mapping failure stays unresolved |
| Check suite, check run, commit status | `Check/v1`, `CommitStatus/v1` | Attached to immutable revision IDs; suite names and run-style timestamps remain null when the suite API does not expose them; provider-only details use a declared companion record |
| Labels, assignees, milestone | Common bounded references | Only values consumed by discovery or detail views enter v0.11.0 |
| Provider timestamps and API observations | Object timestamps plus `Retrieval/v1` | Hosted state and retrieval freshness never share one timestamp |

SoftSchema maturity follows the evidence without weakening checked-in contracts:

1. Exploratory notes may use soft or permissive schemas while field meaning and
   consumers are still being reviewed; they are not conformance artifacts.
2. Every checked-in conformance artifact is enforced from its first machine-checked
   version. Pydantic models compile deterministic schemas, and Python and browser
   consumers validate the same corpus and semantic invariants.
3. Before provider acquisition publishes durable cache entries, the installed host
   registry binds every released contract to its packaged schema, and undeclared fields
   fail.

No artifact in the conformance corpus or released provider cache is permissive.
Persisted timestamps use canonical RFC 3339 UTC strings with required seconds and `Z`.
Zero milliseconds are omitted and a nonzero fraction has exactly three digits.
Adapters convert offsets to UTC and truncate finer precision toward the earlier
millisecond at acquisition, which keeps Python and browser validation and ordering
exact. Provider links use canonical ASCII HTTPS syntax with a lowercase DNS host, no
credentials or default port, and uppercase hexadecimal percent escapes.
Readers accept finite integral JSON numbers and canonical serialization writes integer
YAML; all persisted integers stay within JavaScript’s exact range.

Small values such as `ActorRef`, `RepositoryRef`, `Label`, `MilestoneRef`,
`GitObjectRef`, collection coverage, and `AuthorizationContextRef` are nested `$defs`,
not independently refreshed files.
An actor reference carries enough identity and display information to render when no
full actor resource was fetched.
`AuthorizationContextRef` carries only stable namespace identity: provider kind,
provider instance, anonymous/authenticated mode, a stable opaque principal ID for
authenticated publications, and an optional normalized capability-partition fingerprint
when the provider proves that capability partition changes object visibility.
Display login, observed scopes or capabilities, and observation time belong to the
retrieval observation and never enter the authorization-context key.
Neither record carries a token, credential-store path, environment value, or raw auth
output. If an authenticated adapter cannot resolve a stable opaque principal ID, it
returns a typed authorization-unavailable state instead of publishing into a shared
authenticated namespace.

Issue and change-request records are separate closed contracts.
A GitHub pull request is not also written as an issue record, so common provider fields
do not acquire two authorities.
Shared code may project either type into an in-memory work-item summary.
It does not use an open union or an untyped `data` mapping on disk.

### Identity and Git references

Every provider object stores a minimal `ProviderObjectRef`: provider kind, provider
instance, object kind, and stable opaque provider ID. The owning domain record stores
repository identity, human URL, and repository-local number where applicable.
File paths use a safe digest or encoded resource key; the full provider ID inside the
record is authoritative.
Repository renames change display coordinates, not provider identity or generic cache
identity.

Change requests record:

- stable change-request and repository IDs, provider-native kind, number, URL, title,
  nullable author, normalized state, draft/locked flags, provider timestamps, labels,
  assignees, milestone, and review decision;
- the base repository ID, nullable head repository ID, ref names, and full Git object
  IDs;
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
    provider_opaque_id: U_kgDOExample
    handle: octocat
    url: https://github.com/octocat
  state: open
  draft: false
  locked: false
  created_at: "2026-08-20T12:00:00Z"
  updated_at: "2026-08-26T15:30:00Z"
  closed_at: null
  merged_at: null
  comparison:
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
    merge_commit_oid: null
    merge_commit_availability: not_requested
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
`ChangeRequestComment/v1`, `Review/v1`, and `ReviewComment/v1` use the same
`frontmatter-md` split.
Review YAML owns identity, author, normalized disposition, lifecycle, timestamps, and
relationships; its optional Markdown body owns the untrusted review-summary prose.
Comment YAML holds identity, author, timestamps, minimized/deleted state, links, and any
typed anchor, while its Markdown body holds the untrusted provider prose.
`ChangeRequestIndex/v1`, manifests, retrieval records, threads, checks, status, and
other compact companion objects use `pure-yaml` because their whole payload is
structured or they refer to one of those comment artifacts.

Phase 0 freezes the exact field set, artifact profiles, and enum policy from
representative fixtures.
It may split a field into another typed record, but it cannot replace a modeled field
with an opaque provider payload.

Content and diffs are read from Git by object ID. Provider commits and files are fetched
only when they carry provider-only annotations or prove collection completeness.
`ReviewAnchor` is a closed tagged union.
A file anchor stores the path but no line; a line anchor stores path, side, and one
line; a range anchor stores path plus independently sided `start` and `end` endpoints.
All forms store original commit ID, current commit ID when available, comparison
identity, and explicit current, outdated, unresolved, or unmappable state.
The UI never invents a current line when an anchor cannot be mapped.

Phase 0B.2 freezes the exact fields, enums, path-byte convention, bundle relationships,
and repository-activity semantics in
[Hosted Review Model and Provider Boundary](../../architecture/arch-hosted-review-model.md#review-signal-and-activity-contracts).
Its implementation surface is fixed before provider mapping begins:

| File | Phase 0B.2 responsibility |
| --- | --- |
| `hosted_review/models.py` | Add the closed comment, review, thread, anchor, check, status, and activity models; `validate_*`/`dump_*` entry points; `validate_hosted_review_bundle`; and semantic invariants |
| `hosted_review/artifacts.py` | Add deterministic `serialize_*_artifact` and `validate_*_artifact` functions only for prose-bearing change-request comments, reviews, and review comments |
| `data/hosted-review-format/review-records-conformance.json` | Portable normalized and invalid review, anchor, relationship, check, and status cases |
| `data/hosted-review-format/repository-activity-conformance.json` | Portable commit/change-request projection, ordering, coverage, continuation, and truncation cases |
| `tests/test_hosted_review_record_models.py` | Model, anchor, lifecycle, relationship, and bundle invariants |
| `tests/test_hosted_review_activity_models.py` | Activity kind, freshness, revision, ordering, bound, and partiality invariants |
| `tests/test_hosted_review_artifacts.py` | Opaque Markdown preservation, empty review summary, contract/envelope rejection, and snapshot identity |
| `devtools/check_distribution.py` | Wheel, sdist, and isolated installed-wheel inventory and corpus smoke evidence |

These formats are unreleased and have no independent consumer or persisted released
data.
Phase 0B.2 therefore updates producers, tests, docs, and fixtures together and does
not add compatibility aliases, dual readers, or migration paths.

### Completeness, freshness, and absence

A sync transaction reports `staged`, `committed`, or `failed` independently of the
coverage of any collection it contains.
Every collection entry in a committed resource set reports one of `not_requested`,
`partial`, `complete`, or `unavailable`, plus bounded pagination information.
A missing comments list is therefore not silently interpreted as “no comments.”
Truncation records its reason, limit, and next cursor or page when one exists.
A REST page failure, GraphQL response with `errors`, null resource node, malformed body,
or bounded-runner truncation cannot produce `complete` coverage.
Failure-class partial truncations carry a typed failed retrieval with a matching reason;
bounded partial truncations contain only their successful page retrievals.

Provider `created_at` and `updated_at` describe the hosted object.
Retrieval time, transport, API version, query identity, HTTP validators, rate-limit
observation, display login, observed scopes or capabilities, and normalization version
belong to retrieval metadata.
This prevents a conditional HTTP detail from becoming part of the domain object’s
identity.

`ChangeRequestIndex/v1` is a bounded discovery projection, not a bag of complete PR
records. Each row contains only stable identity, number, URL, title, state, draft state,
nullable author, base/head labels, and provider timestamps needed to choose a PR. It
contains no review or check summary.
The index records its requested state filter and stable sort with a deterministic
unsigned UTF-8 provider-ID tie-breaker, tagged page continuations, declared item, page,
byte, and time bounds, collection state, and remote consistency: `provider_snapshot`,
`best_effort_window`, or `unknown`. The enclosing resource set owns first and last
observation times, per-page retrieval references, coverage, and remote consistency; the
referenced retrieval records own validators, rate-limit observations, and transport
details. The sync manifest closes over those records so an unchanged index can reuse its
immutable snapshot. Rows deduplicate by stable provider ID. Changing query inputs
produces a new immutable observation; it does not silently reinterpret an existing
index. Reviews, threads, checks, descriptions, and Git-ref availability belong to the
selected PR bundle and are never multiplied across list rows.

`complete` means the provider reported the requested query exhausted before an item,
page, byte, or time bound was hit.
Hitting a bound yields `partial` plus its truncation reason and continuation.
Completeness never means every PR resource is hydrated or that a best-effort multi-page
window was observed at one provider instant.

A v1 tombstone requires a typed provider deletion event or deleted marker for the exact
provider object and repository after a matching live snapshot was observed under the
same authorization context.
The prior live observation may come from an earlier committed snapshot.
A provider deletion event time, or the retrieval time of a deleted marker, must follow
it; the deletion retrieval and tombstone observation must be causally ordered inside the
new committed sync transaction.
A GitHub `404`, GraphQL null node, authentication failure, permission loss, rate limit,
or resource never fetched is `not_found_under_context`, `unavailable`, or another typed
outcome—not deletion.
Those states retain the last-known observation and never synthesize a tombstone.
Corroborated absence remains deferred until a later contract has a profile-defined
exhaustive collection; the filtered pull-request index cannot supply that evidence.

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
    └── <auth-context-key>/
        ├── repository/
        │   ├── current.yml
        │   └── last-complete.yml
        ├── pull-requests/
        │   ├── index/
        │   │   └── <query-key>/
        │   │       ├── current.yml
        │   │       └── last-complete.yml
        │   └── <number>/
        │       ├── current.yml
        │       └── last-complete.yml
        └── issues/<number>/current.yml       # later: mb-9rrc
```

An object snapshot is immutable after publication.
Its snapshot ID is derived from its contract ID and canonical normalized payload.
Retrieval time, validators, query identity, and rate-limit state live in the sync
manifest, so a conditional response can reuse an unchanged object instead of writing a
byte-different copy.
A resource set names the exact object snapshots and collection states for one logical
repository, change request, or query target.
A sync manifest names the resource sets, transaction state, authorization context,
retrieval evidence, and failures that make up one acquisition.
`<auth-context-key>` is a safe digest of only the stable, non-secret
`AuthorizationContextRef` identity fields.
Observation time, display login, and observed scopes or capabilities stay in retrieval
metadata, so a repeat preflight for the same principal advances the same pointers while
a validator or denial observed under one principal cannot mutate another principal’s
pointers.
`<query-key>` is a deterministic digest of the complete normalized index query,
including provider instance, state filter, sort, and declared bounds.
The plugin may nominate one conventional query as the UI default, but it is an alias to
that exact key rather than a queryless second authority.
Each small `current.yml` is a `ProviderViewPointer/v1` that names an immutable resource
set and a committed manifest; `last-complete.yml` retains the newest resource set whose
declared required-collection profile is complete.
The browser never follows staging files or a half-written multi-page response.

An interrupted, invalid, or failed transaction leaves both pointers untouched.
A valid committed manifest may contain explicitly partial or unavailable collections and
become `current.yml`, allowing the UI to show the newest honest observation while
`last-complete.yml` stays readable.
Every profile slot required for complete fallback must have an attempted outcome before
current advances; `not_requested` remains valid for optional slots but a no-attempt
required slot cannot replace a useful observation.
The transaction state therefore never doubles as a completeness flag.

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
A committed provider refresh atomically publishes a new manifest.
A failed refresh leaves the pointers unchanged and exposes its staged diagnostics; a
structurally valid partial refresh may become current with its partiality visible and
the previous complete manifest retained at `last-complete.yml`.

The provider process performs network work with no application-home, entry, or provider
lock held. Publication then acquires the repository-entry lock before the
provider/resource lock, revalidates the entry lease and authorization context, and
atomically publishes the manifest and pointer.
The application-home lock is reserved for layout migration and global sweeps; it is
never nested inside an entry or provider lock.

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
| Snapshots referenced by current or `last-complete` | They are the newest observation and complete fallback | Never, while either pointer retains them |
| Snapshots referenced by the bounded diagnostic predecessor | One prior generation is worth keeping for diagnosis after a bad refresh | Replaced only after the next validated generation commits |
| Snapshots referenced by an explicit archival pin | The user chose to preserve that observation | Explicit unpin or purge only |
| Snapshots referenced only by older superseded manifests | They exceed the bounded diagnostic policy | Older manifests and snapshots only they reference are collectable |
| Snapshots referenced by no retained manifest | Nothing can reach them | Swept with the superseded manifests that orphaned them |

The global sweep briefly uses the application-home lock only to enumerate eligible
entries. Per-entry work then follows entry lock → provider/resource lock and honors
reader leases; it never collects a snapshot a live session is serving.
Offline or deleted sources follow the same reachability rule, so an old unreachable
generation does not accumulate forever while the last validated reachable observation is
never automatically removed.

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
Every application-home directory containing repository or provider content is `0700` and
every file is `0600` on POSIX; Windows uses a current-user-only ACL with the same
intent. Metabrowser refuses remote acquisition or provider publication when any cache
ancestor is a symlink, is owned by another principal, is group/world accessible, or
cannot be verified and repaired.
An explicitly configured permissive `METABROWSER_HOME` produces an actionable refusal,
not a warning followed by a private write.
Ordinary read-only browsing of a local path outside the application home remains
available.

Schema selection comes from the installed registry, never from a path inside a cache
file. Provider object ids and URLs never become filesystem paths without safe encoding
and containment checks.
Credentials stay in `gh`, the OS credential store, or an explicit provider adapter; the
plugin reports which source it used and never reads a secret into a record, a log, or a
browser response. Browser renderers insert provider text through text nodes or the
existing untrusted Markdown path, never `innerHTML`; provider-supplied links accept
validated `https` URLs only.

## Implementation Coordinates

The implementation uses domain and provider plugins over a neutral provider-resource
service. `src/metabrowser/provider_resources/` owns content-neutral identity and storage
records, the shared minimal `HostedRepository/v1` contract and repository-summary
profile, publication validation, and the store behind `ProviderResourceStorePort`.
`hosted_review` owns change-request contracts, routes, and views; the future
`hosted_releases` plugin owns release contracts, routes, and views.
`github` owns URL syntax, `gh`, GitHub response mapping, and named GitHub companion
records. Core owns plugin mounting, safe repository services, subprocess policy, and
lifecycle. Phase 0B.1 stages the unreleased neutral records beside their first consumer;
`mb-s0gv` moves them without compatibility aliases before `mb-i3xc` implements the store
or another domain plugin consumes them.

### Core and plugin-SDK changes

| File | Existing seam | Planned change |
| --- | --- | --- |
| `src/metabrowser/plugin_loader/manifest.py` | `PluginManifest`, `DataHookSpec`, file `KindRule` and `ViewSpec` | Keep the browser and file-kind manifest unchanged in Phase 0C.1; later add `ResourceKindSpec`, `RouterSpec`, `AddressSpaceSpec`, `ProviderUrlReducerSpec`, and `ProviderAdapterSpec` only when their browser, route, or lifecycle surfaces ship |
| `src/metabrowser/plugin_loader/capability_types.py` | `ArtifactContractSpec`, `ConformanceCorpusSpec`, `BrowserParserSpec`, `ArtifactValidationContext`, `CapabilitySet` | Define the dependency-light public declaration surface, including explicit browser consumption, immutable packaged corpus, and self-contained browser-parser evidence, without loading schema parsers, validators, or discovery during an ordinary `import metabrowser` |
| `src/metabrowser/plugin_loader/capability_discovery.py` | `discover_capability_sets` | Load versioned `metabrowser.capabilities.v1` entry points only from installed distributions; reject duplicate providers and any partial discovery result; never load backend capabilities from operator directories or viewed data |
| `src/metabrowser/plugin_loader/artifact_contracts.py` | `build_contract_registry`, `build_resource_profile_registry`, `validate_record`, `validate_artifact`, `serialize_artifact` | Install trusted contract and publication-profile objects returned by capability factories; verify exact schema, corpus, and browser-module bytes separately from the independently recomputed logical schema identity; artifacts may name but never supply a schema, profile, parser, renderer, or Python import path |
| `src/metabrowser/plugin_loader/artifact_inventory.py` | `installed_artifact_inventory`, `check_installed_evidence`, `validate_installed_evidence` | Derive one generic inventory from installed contract/profile declarations; require positive and negative selected cases; and verify structural, semantic, deterministic serialization, and declared artifact-profile round-trip evidence without a built-in contract-name list |
| `src/metabrowser/plugin_loader/static_assets.py` | `_resolve_sidekick`, `build_plugin_routes` | Build one Starlette `Mount` per installed router and preserve its methods, streaming, headers, and status codes; keep exact data hooks for simple GET/POST models |
| `src/metabrowser/plugin_loader/provider_urls.py` (new) | — | Load trusted installed reducers; arbitrate `NotApplicable`, `Reduced`, and terminal `Rejected` outcomes; refuse duplicate scheme/host claims; and dispatch without importing a provider in cache or CLI code |
| `src/metabrowser/plugin_loader/provider_capabilities.py` (new) | `build_provider_registry`, `create_provider`, `close_provider`, `close_all` | Build the provider/instance capability registry, inject provider-neutral ports, reject duplicate claims, and await adapter cancellation and close |
| `src/metabrowser/plugin_loader/provider_addresses.py` (new) | `encode_provider_address_atom`, `decode_provider_address_atom`, `parse_hosted_address`, `format_hosted_address` | Encode provider instance, repository opaque ID, and provider-object opaque ID as typed canonical unpadded-base64url atoms; reject wrong roles, padding, noncanonical encodings, invalid UTF-8, dot segments, and bounds violations |
| `src/metabrowser/plugin_api.py` | `served_root`, path resolvers, `register_root_callback`, `ProviderResourceStorePort` | Expose typed entry identity, selected-ref job, materialization-lease, and neutral provider-resource publication ports; expose no cache path and no provider schema |
| `src/metabrowser/provider_resources/models.py` (new, `mb-s0gv`) | provider kind/instance scalars, `ProviderObjectRef`, `RepositoryRef`, `AuthorizationContextRef`, generic object/collection targets, `ProviderBinding`, `Retrieval`, `ResourceSet`, `ProviderSyncManifest`, pointers, tombstones, profile declarations, closure validators, and the shared minimal `HostedRepository` | Own provider-content-neutral identity, binding, publication, and repository-summary records plus trusted-profile application independently of any domain plugin; `ChangeRequest`, `Release`, and their companions remain domain-plugin records |
| `src/metabrowser/provider_resources/store.py` (new, `mb-i3xc`) | `ProviderStore`, `stage_snapshot`, `publish_manifest`, `read_current`, `read_last_complete`, `lease_snapshot`, `reclaim_snapshots` | Implement auth-scoped immutable snapshots, atomic query-key pointers, reader leases, diagnostic retention, and bounded reachability reclamation behind the port |
| `src/metabrowser/provider_process.py` (new, `mb-y1ax`) | mirrors `git/process.py` policy | `run_provider_command(stdin=...)`, `terminate_provider_command`, bounded response parsing, and typed missing/timeout/output/cancelled failures for no-shell provider CLIs |
| `src/metabrowser/static/plugin-sdk.js` | `registerView`, `fetchPluginData` | Add registered route-backed resource kinds, disposal-returning `registerAddressSpace`, `registerNavPanel`, and a provider-neutral bounded virtual-collection controller |
| `src/metabrowser/static/plugin-address-spaces.js` (new) | `createAddressSpaceRegistry`, `parseAddress`, `formatAddress`, `applyAddress`, `replaceRoot`, `disposeAddress` | Arbitrate one browser-address owner and run its startup, popstate, preview, replacement, and disposal lifecycle without provider branches |
| `src/metabrowser/static/navigation.js` | `href`, `parse`, `commitHref` | Dispatch parse, format, selection application, popstate, and preview claims through the one installed address-space owner; preserve core address behavior |
| `src/metabrowser/static/app.js` | internal `registerNavPanel`, `removeNavPanel`, preview claims | Publish the narrow SDK adapters; start and dispose plugin address spaces and panels on replacement/root change; keep preview ownership generation-checked |
| `src/metabrowser/static/git-history-window.js` | `createPageCache`, `createVirtualWindow` | Extract or publish the provider-neutral paging/virtualization primitives once; update `git-panel.js` and hosted review together, with no compatibility wrapper |
| `src/metabrowser/cli/show_cli.py` | `run_show` | Resolve plugin address spaces and resource kinds through the same parser, model, and view registry as the browser, including `/hosted/...` |
| `src/metabrowser/server.py` | `build_plugin_routes`, `_lifespan` | Mount plugin routers before catch-all shells, construct registered provider adapters with explicit dependencies, await their cancellation/close on shutdown, and keep all provider routes in plugins |

`RouterSpec` is the implementation of `mb-xzj3`; `AddressSpaceSpec` is the separate
browser lifecycle in `mb-6mle`; `ProviderAdapterSpec` is the capability and lifespan
registry in `mb-ji83`. The router is required because an exact single-segment data hook
cannot honestly own
`/hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>`
or resource routes with path parameters and conditional responses.
The address-space spec is required because mounting HTTP does not teach navigation to
parse, format, restore, or dispose that address.
Operator-directory plugins remain JavaScript-only.
Artifact contracts and resource profiles use the separately versioned installed-Python
capability group and do not enter browser plugin discovery, `/plugin-static`, or
`window.metabrowser`. The later browser and route capabilities are additive only while
existing manifests and JavaScript calls keep their signatures and behavior, so optional
declarations may retain SDK 0.6 with plugin-author documentation and a `CHANGELOG.md`
note. If implementation changes an existing signature or semantic contract,
`PLUGIN_SDK_VERSION` and every built-in manifest change in the same commit; no dual
contract is kept.

### Hosted-review plugin

| File | Key types and functions | Responsibility |
| --- | --- | --- |
| `src/metabrowser/builtin_plugins/hosted_review/manifest.toml` | kinds, views, router, scripts, styles | Deferred until the first route-backed kind or view; Phase 0C.1 registers only installed Python capabilities and exposes no browser asset root |
| `models.py` | `ChangeRequest`, comments, reviews, threads, anchors, checks, statuses, and activity | Closed hosted-review domain models; Phase 0B.1 neutral identity/storage records and `HostedRepository` move to `provider_resources/models.py` under `mb-s0gv` before store implementation |
| `resource_profiles.py` | change-request profile declarations and `resolve_resource_profile` | Trusted hosted-review publication declarations for ordered collection contracts, cardinality, pagination, and last-complete requirements; the repository-summary profile moves with `HostedRepository` to `provider_resources` |
| `contracts.py` | `HOSTED_REVIEW_CONTRACTS`, `compile_contracts`, `validate_contract_values`, `provider_resource_capabilities`, `hosted_review_capabilities` | Plugin-local SoftSchema declarations consumed by the installed host registry, semantic validation, deterministic schema compilation, and installed capability factories |
| `artifacts.py` | `serialize_change_request_artifact`, `parse_frontmatter_artifact`, `validate_change_request_artifact`, `snapshot_identity` | Encode only a validated ChangeRequest and decode enforced `frontmatter-md` artifacts through frontmatter-format without owning filesystem publication; hash normalized YAML plus the complete Markdown body, including an empty body |
| `service.py` | `HostedReviewProvider`, `get_repository`, `get_change_request`, `list_change_requests`, `refresh_resource` | Change-request orchestration over `ProviderResourceStorePort` with typed completeness, freshness, and failure states |
| `routes.py` | `build_router`, `repository_resource`, `change_request_resource`, `change_request_index`, `hosted_resource_shell` | Plugin-owned read routes and canonical hosted-resource document shell |
| `hosted-review-model.js` | `parseChangeRequest`, then parsers for the remaining browser-consumed records | Browser validation against the same contract corpus; the Phase 0A module stays unregistered, DOM-free, and network-free |
| `data/hosted-review-format/change-request-conformance.json` | `base_document`, named valid/invalid mutations | Portable Python/browser oracle for closed keys, lifecycle, identity relationships, canonical timestamps and URLs, exact integer bounds, and Git object IDs |
| `hosted-review-view.js` | `prepareChangeRequestView`, `mountChangeRequestView`, `disposeChangeRequestView` | Compose metadata, Markdown description, reviews/checks, revision links, and File Diff Format |
| `hosted-review-panel.js` | `createPullRequestPanel`, `loadIndexPage`, `openChangeRequest`, `dispose` | Virtual Pull Requests collection and item-like/folder-like rows |
| `index.js`, `styles.css` | registrations and presentation | Register views/panels and use existing design tokens with measured loading tiers |

The plugin router returns provider-neutral documents and projections.
It calls the Git comparison adapter by full object IDs and the existing revision-content
routes for base or head files; it neither copies provider fields into File Diff Format
nor reads a GitHub snapshot directly.
The exact first routes are
`/api/hosted-review/<provider-kind>/<instance-key>/<repository-key>/repository`,
`/change-requests?query_key=<key>`, `/change-requests/<change-key>`, and
`/change-requests/<change-key>/comparison` under that repository prefix, plus the
browser address
`/hosted/<provider-kind>/<instance-key>/<repository-key>/change-request/<resource-key>[/<inner>]`.
`metab --api` and `metab --show` use those exact registrations rather than a parallel
CLI resolver.

### GitHub provider plugin

| File | Key types and functions | Responsibility |
| --- | --- | --- |
| `src/metabrowser/builtin_plugins/github/manifest.toml` | URL reducer, provider adapter, optional companion views | Register GitHub without adding a GitHub branch to core |
| `urls.py` | `reduce_github_url`, `github_clone_source`, `parse_github_selection` | Recognize public and configured Enterprise repository/tree/blob/commit/pull forms and return an ordinary source plus selection candidates |
| `auth.py` | `preflight_gh_auth`, `resolve_principal_identity`, `auth_recovery` | Parse non-secret `gh auth status --active --hostname ... --json hosts`, resolve the stable opaque principal through the fixed bounded identity request, separate stable context identity from volatile observations, and produce typed recovery states |
| `queries.py` | `viewer_identity_request`, `repository_request`, `change_request_request`, `change_request_index_request`, `reviews_request`, `checks_request` | Fixed REST paths and checked-in GraphQL documents, including the fixed `/user` identity request; explicit JSON variables, query hashes, API/Accept profiles, and one-page bounds |
| `adapter.py` | `GitHubGhAdapter`, `request_page`, `parse_included_response`, `get_repository`, `get_change_request`, `list_change_requests` | Implement the common provider port with `gh api --include --input - --hostname`; parse allowlisted metadata, body, GraphQL errors, and nulls; never use `gh pr view`, field flags, `--paginate`, `--cache`, or verbose output |
| `mapping.py` | `map_repository`, `map_change_request`, `map_change_request_comment`, `map_review`, `map_thread`, `map_review_comment`, `map_check`, `map_status` | Normalize each response immediately into common records or a declared GitHub companion; preserve an optional review summary as the `Review/v1` Markdown body |
| `sidekick.py` | `build_provider`, `refresh_repository`, `refresh_change_request`, `refresh_index` | Bind the adapter to the hosted-review service and repository job/ref ports |

The URL reducer can ship before `gh` acquisition.
Repository and branch URLs therefore use generic Git credentials and the repository
cache; only hosted-review metadata and direct PR hydration require the provider adapter
and `gh` authentication.

### Fixtures, tests, goldens, and parity

| Surface | Files |
| --- | --- |
| Common contracts | `tests/fixtures/hosted_review/valid/`, `invalid/`, `tests/test_hosted_review_models.py`, `tests/test_hosted_review_contracts.py`; include review artifacts with and without a Markdown summary body, and run the same corpus through every Python and browser parser |
| Coverage oracle and GitHub mapping | `tests/fixtures/github/oracle/`, `tests/test_github_coverage.py`, `tests/test_github_mapping.py` |
| Auth and transport | `tests/test_provider_process.py`, `tests/test_github_auth.py`, `tests/test_github_adapter.py` |
| Atomic provider cache | `tests/test_hosted_review_store.py`, `tests/test_hosted_review_service.py`: auth contexts, staged/committed/failed transactions, partial current plus `last-complete`, lock order, leases, offline/deleted retention, and reclamation races |
| Plugin routing and registries | `tests/test_plugin_manifest.py`, `tests/test_plugin_routes.py`, `tests/test_plugin_address_spaces.py`, `tests/test_provider_capabilities.py`, `tests/test_hosted_review_routes.py` |
| View and nav lifecycle | `tests/dom/hosted-review-session.js` runs exact production address, document, panel-window, selection, restoration, root-replacement, and disposal owners; focused component cases stay in `hosted-review-view.js` and `hosted-review-panel.js` |
| CLI goldens | `tests/golden/cli-github-repository.tryscript.md`, `cli-github-pr-open.tryscript.md`, `cli-github-pr-index.tryscript.md`, `cli-github-pr-offline.tryscript.md`, `cli-ui-hosted-review.tryscript.md` |
| Registered formats and surfaces | `devtools/check_artifact_contracts.py`, `devtools/check_parity.py`, `docs/project/architecture/arch-external-resources-and-views.md`, `docs/project/architecture/arch-views-models-routes.md`, `tests/test_artifact_inventory.py`, `tests/test_check_artifact_contracts.py`, `tests/test_views_models_routes.py`, `tests/test_distribution_policy.py` |

No test contacts GitHub or a real credential store.
Recorded responses are scrubbed inputs to mapping and coverage tests; fake executable
fixtures exercise the exact provider-process path.
They include hostile structured metadata: markup-like titles and actor names, bidi and
control characters, unsafe URL schemes, oversized values, malformed included-response
headers, GraphQL `data` plus `errors`, null nodes, and output truncation.
A production-mount browser session proves text-node insertion, untrusted Markdown,
HTTPS-only provider links, preview ownership, and disposal rather than asserting a test
renderer. A separate opt-in live smoke test may validate public GitHub and Enterprise
behavior, but it is not part of `make verify` and cannot substitute for the hermetic
suite.

## Phased Implementation Plan

The design boundary is fixed before network or view work.
Implementation follows the user-visible dependency chain rather than treating “GitHub
support” as one feature.

### Phase 0: Hosted Review Format and plugin boundary (`mb-63ym`)

Phase 0 is decomposed into mergeable, file-level beads so the contract can mature
without registering a partial product surface:

Phase 0A adds no manifest, route, view, cache, network, credential, provider, SDK, or
dependency behavior; it is a dormant semantic and artifact-codec kernel.

| Slice | Bead | Files and functions | Exit evidence |
| --- | --- | --- | --- |
| 0A.1 contract freeze | `mb-u8n8` | This plan and `arch-hosted-review-model.md`; freeze `ProviderObjectRef`, `RepositoryRef`, `RevisionRef`, `ComparisonRef`, `ChangeRequest`, frontmatter authority, canonical scalars, and dormancy | Design and implementation names agree |
| 0A.2 Python kernel | `mb-tf5b` | `hosted_review/models.py`: closed/frozen references and `ChangeRequest`, `validate_change_request`, `dump_change_request` | Focused lifecycle, identity, availability, count, and hostile-text tests |
| 0A.3 artifact codec | `mb-ja7z` | `hosted_review/artifacts.py`: `serialize_change_request_artifact`, `parse_frontmatter_artifact`, `validate_change_request_artifact`, `snapshot_identity` | Only a validated model can receive the enforced contract marker; deterministic bytes preserve nulls, empty collections, and the complete opaque Markdown body |
| 0A.4 portable corpus | `mb-sezk` | `data/hosted-review-format/change-request-conformance.json` and Python harness | Named open, draft, merged-fork, unknown-state, invalid-scalar, and cross-record cases |
| 0A.5 browser kernel | `mb-wiuu` | `hosted-review-model.js`: `parseChangeRequest`; browserless Node harness | Python and exact production JavaScript accept and reject the same corpus; unexpected defects escape |
| 0A.6 installed evidence | `mb-02bg` | `devtools/check_distribution.py` plus the architecture map | Wheel and sdist contain the kernel; isolated-wheel validation passes; discovery remains the existing nine plugins |
| 0A.7 stacked review | `mb-c08x` | Git branch and draft pull request based on `codex/v011-hosted-review-design` | Review shortcuts, `make verify`, tbd sync, exact-stack diff, and final CI summary |
| Stack landing | `mb-n2ro` | Completed formal phase pull requests, fetched bases, and each exact phase diff | After explicit approval, land in order; retarget the next phase; recheck scope; rerun `make verify`; obtain final green CI; and confirm `main` contains each merged layer |
| 0B.1 storage records | `mb-pnz5` | One formal pull request: architecture/spec freeze; `models.py` provider namespace, auth, retrieval, generic object/collection publication, repository, tombstone, and index records; trusted `resource_profiles.py`; existing JavaScript namespace validators; three portable corpora; focused tests; distribution proof | Closed auth-scoped publication, repository, index, extensible resource-profile, and failure-state fixtures with independent review and green CI |
| 0B.2 review records | `mb-915y` coordinates `mb-n9fo` and `mb-qpbu` | `models.py` and `artifacts.py`: comments, reviews, threads, anchors, checks, statuses, activity, review, and formal PR publication | Relationship, partiality, body/no-body fixtures, independent review, `make verify`, and green CI |
| 0B.3 GitHub oracle | `mb-rla6` coordinates `mb-oc1h` and `mb-e95m` | `tests/fixtures/github/oracle/`, `test_github_coverage.py`, mapping matrix, review, and formal PR publication | Every common field is observed, derived, or explicitly unavailable; inputs are scrubbed and public-safe; CI is green |
| 0C.1 SoftSchema contracts | `mb-lqae` coordinates `mb-52iz` and `mb-vepa` | Plugin-local `contracts.py`, versioned installed-Python capability discovery, artifact-contract and resource-profile registries, deterministic packaged schemas, explicit built-in schema inclusion and isolated-wheel smoke in `check_distribution.py`, exact first-party dependency selection owned by `mb-4gnu`, review, and formal PR publication | Enforced contract/profile registry and Python/browser/schema/corpus agreement with green CI; named built-in schemas survive wheel installation; no manifest, route, kind, view, or static asset is registered |
| 0C.2 format gate | `mb-dhz8` coordinates `mb-vors` and `mb-ci0t` | Generic contract/profile inventory, inventory-driven distribution and installed-evidence gates, architecture registration, parity evidence, review, and formal PR publication | Every shipped contract/profile has its schema, semantics, producer, consumer, fixture, installed-artifact check, and green CI without a hard-coded built-in list |

Phase 0C.2 adds no cache, provider, network, route, kind, view, manifest, or
static-asset surface.
Its maintained implementation coordinates are:

| File | Functions or evidence | Phase 0C.2 responsibility |
| --- | --- | --- |
| `plugin_loader/artifact_inventory.py` | `installed_artifact_inventory`, `check_installed_evidence`, `validate_installed_evidence` | Project deterministic contract/profile metadata; require positive and negative selected cases; and run each valid case through structural, semantic, deterministic serialization, and artifact-profile round-trip checks |
| `devtools/check_artifact_contracts.py` | `check`, `main` | Compare every installed declaration and exact profile semantics with the architecture inventory; reject missing, orphaned, duplicated, or inexact rows; and execute browser-consumed parser bytes against VM-realm inputs with only context-native `TextEncoder`, one-shot UTF-8 `TextDecoder`, `atob`, and `btoa`, imports and dynamic code disabled, and type-sensitive JSON-domain preservation checks |
| `devtools/check_distribution.py` | isolated source-distribution and wheel inventory checks | Reconcile provider entry points with project metadata, then derive packaged schemas, corpora, parser modules, and contract/profile counts from each installed artifact rather than a built-in filename list |
| `arch-external-resources-and-views.md` | installed contract and profile tables | Register the exact current format surface while labeling browser parser modules as evidence rather than runtime plugin bindings |
| `tests/test_artifact_inventory.py`, `tests/test_check_artifact_contracts.py`, `tests/test_distribution_policy.py` | focused corpus, architecture-drift, and distribution regressions | Pin the generic gate and prevent a source-tree-only declaration from passing installed-artifact verification |

Phase 0B.3 is a no-network evidence and reconciliation slice.
The oracle may require the smallest correction to an existing common model when exact
provider evidence disproves the current contract.
Such a correction updates every affected producer, consumer, corpus, test, and document
in this slice; it does not justify speculative fields, provider behavior, or a new
runtime surface.

| Phase 0B.3 surface | File- and function-level responsibility | Exit evidence |
| --- | --- | --- |
| Python common model | `builtin_plugins/hosted_review/models.py`: reconcile `RevisionRef`, `GitObjectRef`, `ChangeRequest`, `ChangeRequestIndexRow`, and `Check` validators only where the oracle proves nullability, identity, or lifecycle facts | Existing public validators accept every corrected corpus record and continue to reject invented or internally inconsistent states |
| Browser common model | `builtin_plugins/hosted_review/hosted-review-model.js`: keep `parseChangeRequest` and its nested reference/actor checks aligned with the evidence-driven Python corrections | Exact production JavaScript accepts and rejects the same ChangeRequest corpus as Python |
| Portable corpora | `change-request-conformance.json`, `change-request-index-conformance.json`, `review-records-conformance.json`, and `repository-activity-conformance.json`: encode nullable authors, deleted-fork repository identity, unavailable original revisions, suite/run timestamp distinctions, and activity projection limits | All four corpora pass Python and applicable browser conformance harnesses with named valid and invalid cases |
| Focused common-model tests | `test_hosted_review_models.py`, `test_hosted_review_record_models.py`, and `test_hosted_review_activity_models.py`: pin each corrected invariant and its counterexample | Focused hosted-review model, record, and activity suites pass |
| Public evidence oracle | `tests/fixtures/github/oracle/manifest.json`, request documents, reduced response files, `field-inventory.json`, and `hostile-synthetic.json`; `tests/test_github_coverage.py`: validate exact request provenance, closed response shapes, RFC 6901 pointers, field/value dispositions, executable identity recipes, public safety, and runtime/package isolation | Every modeled field and closed value has mechanically resolved evidence or an explicit owned/unavailable disposition; no test contacts a network |
| Durable documentation | This plan, `arch-hosted-review-model.md`, and `arch-views-models-routes.md`: record the proven provider boundary, test-only oracle authority, and absence of adapter/route/registry behavior | Documentation agrees with the checked contract and names Phase 0C or later for unimplemented runtime surfaces |

Phase 0B.1 is one pull request with the following bead sequence:

| Bead | Internal result |
| --- | --- |
| `mb-tznv` | Freeze namespace, publication, query-key, consistency, and tombstone contracts in the plan and architecture |
| `mb-fvbn` | Apply canonical provider kind and instance scalars to Python and the existing ChangeRequest browser parser |
| `mb-vyb2` | Add stable authorization-context identity, retrieval observations, and deterministic auth keys |
| `mb-jgcm` | Add resource sets, pointers, manifests, collection coverage, continuations, failures, and tombstone evidence |
| `mb-yc62` | Add auth-independent provider bindings, hosted-repository records, rename validation, and explicit rebind conflict detection |
| `mb-28zj` | Add bounded query-keyed change-request indexes, deterministic ordering, pagination, and consistency claims |
| `mb-iwsx` | Generalize provider-object/provider-collection targets, collection pages, neutral storage contract IDs, and trusted namespaced resource-profile declarations; prove a synthetic release index adds no storage-kernel variant |
| `mb-k28s` | Add portable storage, repository, and index corpora plus focused semantic and installed-artifact evidence |
| `mb-1utg` | Run independent reviews and `make verify`, publish the formal pull request with `gh`, and wait for final green CI |

Every remaining Phase 0 slice uses the same explicit implementation/publication pair:

| Formal phase PR | Implementation bead | Review and publication bead | Exact stacked base |
| --- | --- | --- | --- |
| 0B.2 | `mb-n9fo` | `mb-qpbu` | Green Phase 0B.1 head |
| 0B.3 | `mb-oc1h` | `mb-e95m` | Green Phase 0B.2 head |
| 0C.1 | `mb-52iz` | `mb-vepa` | Green Phase 0B.3 head |
| 0C.2 | `mb-vors` | `mb-ci0t` | Green Phase 0C.1 head |

Each phase coordinator closes only after its implementation and publication children are
complete. `mb-n2ro` depends on every publication bead and alone owns explicit-approval
landing, retargeting, exact-diff revalidation, and post-land CI; no phase implementation
or publication bead merges another phase.

- [x] Write the provider-neutral contract inventory as Pydantic models and deterministic
  compiled SoftSchema contracts, using simple closed objects and local `$defs`.
- [x] Use `frontmatter-md` for `ChangeRequest/v1`, with all consumed fields in YAML and
  the provider description as the reader-facing Markdown body; use the same profile for
  reviews, top-level comments, and review comments with Markdown prose, and `pure-yaml`
  for indexes, manifests, and compact structured companion records.
- [x] Define stable provider and local IDs, repository refs, Git object refs, provider
  timestamps, non-secret stable authorization-context identity separate from retrieval
  observations, transaction state, completeness, pagination consistency, tombstone
  proof, unknown enums, and explicit provider companion records.
- [x] Keep provider storage content-neutral: persist generic provider-object or
  provider-collection targets and namespaced profile IDs, then resolve ordered
  collection contracts, cardinality, pagination, and last-complete requirements only
  through the trusted installed resource-profile registry.
- [x] Define repository, change request, top-level comment, review, thread, review
  comment, file/line/range anchor, check, status, and activity relationships without an
  opaque payload or provider-shaped view model.
- [x] Build normalized and invalid fixtures for open, closed, merged, draft, forked,
  deleted, inaccessible, partial, paginated, direct-addressed, outdated-anchor, and
  unknown-enum cases.
- [x] Add one GitHub terminology-to-common-model mapping matrix and prove every common
  field has a consumer; do not add speculative GitLab-only fields.
- [x] Capture the scrubbed response oracle and require every modeled field to be
  observed, deterministically derived, Metabrowser-owned, or explicitly
  optional/unavailable.
- [x] Register the installed contract and resource-profile formats in the architecture
  map and add a generic inventory check that fails when a declaration lacks its schema,
  semantics, producer, consumer, positive/negative corpus evidence, deterministic
  artifact-profile round trip, browser-parser evidence when browser-consumed, profile
  closure, installed-artifact proof, or exact architecture row.
  Keep proposed routes, resource kinds, views, cache paths, and provider adapters
  unregistered until their implementation phases.

### Phase 1: Robust generic repository cache (`mb-ire2` through `mb-dg00`)

This phase is owned by the
[repository-library plan](plan-2026-08-11-open-repo-from-git-url.md), but it is the
first implementation prerequisite here.

- [ ] Publish the versioned application home, strict layout and entry records, locks,
  atomic no-replace promotion, quarantine, trash, and deterministic inspection routes.
- [ ] Enforce owner-only application-home permissions through `mb-xa0p`, and freeze the
  home → entry → provider/resource lock order without holding any lock across network
  work.
- [ ] Acquire one generic Git URL into a pinned, reusable entry through the single
  bounded Git process boundary.
- [ ] Route the cached `gitroot` through the inventory coordinator lifecycle and prove
  offline reuse, interruption recovery, and future-format refusal in goldens.

### Phase 2: GitHub repository and branch URL opening (`mb-12cz`, `mb-ew38`, `mb-z335`, `mb-2xq7`)

The GitHub implementation after Phase 0 also uses one formal stacked pull request per
phase. Every publication bead requires independent review, the review shortcut,
`make verify`, a formal draft PR created with `gh`, exact base/head branch names and
OIDs, final green CI, and registration with `mb-n2ro`; it never merges the PR. The next
implementation depends on the preceding green publication bead.
Before Phase 2A begins, `mb-j439` records one named integration head and immutable OID
that contains the exact green Phase 0C.2, generic repository-cache, cache-golden,
untrusted-profile, and Git-status prerequisite commits.
It verifies all five as ancestors and runs `make verify`; Phase 2A cannot choose one
prerequisite lineage while omitting another.

| Formal phase PR | Implementation beads | Review/publication bead | Exact stacked base |
| --- | --- | --- | --- |
| 2A repository URL open | `mb-12cz`, `mb-ew38` | `mb-innz` | Exact named convergence head and OID recorded by `mb-j439`, containing every format, cache, trust, and status prerequisite |
| 2B branch materialization | `mb-z335`, `mb-2xq7` | `mb-9aku` | Green Phase 2A head |
| 3A provider foundation | `mb-y1ax`, `mb-p4sw`, `mb-ji83`, `mb-s0gv`, `mb-i3xc`, `mb-2oxp` | `mb-k7lc` | Green Phase 2B head |
| 3B direct PR cache | `mb-h64t` | `mb-cpco` | Green Phase 3A head |
| 4A direct PR view | `mb-xzj3`, `mb-6mle`, `mb-83w0`, `mb-81p5` | `mb-79sz` | Green Phase 3B head; direct addressing and viewing require no discovery index |
| 3C bounded PR index | `mb-lnkl` | `mb-bue2` | Green Phase 4A direct-view head |
| 4B PR navigation | `mb-uh6p`, `mb-iw1v` | `mb-r596` | Green Phase 3C index head |
| 4C review anchors | `mb-rldc` | `mb-mx8q` | Green Phase 4B head |

`mb-n2ro` is the sole approval-gated landing coordinator for Phase 0 and these v0.11
GitHub phases. A later branch may be constructed on the exact green PR head while an
earlier PR waits to land, but no phase skips its publication bead or changes its
recorded base silently.

- [ ] Register the GitHub reducer through the provider-neutral URL plugin seam and
  recognize canonical repository, tree, blob, commit, raw, and `/pull/<number>` forms;
  reject credentials, ambiguous hosts, and syntax the grammar does not own.
- [ ] Require declared scheme/host claims and `NotApplicable`, `Reduced`, or terminal
  `Rejected` outcomes; reject overlapping claims and prove reducer ordering cannot
  change an address’s owner.
- [ ] Resolve or acquire the generic repository entry before invoking a provider
  adapter, and reuse the canonical escaped path-identity codec for every selection.
- [ ] Resolve any advertised and authorized branch, including names with slashes, to a
  full object ID and serve it from a detached materialization without moving the pinned
  cache entry.
- [ ] Preserve a directly addressed PR target even when the provider index is absent,
  stale, partial, or does not contain that number.
- [ ] Apply the untrusted-content profile before serving fetched repository or provider
  content.

### Phase 3: GitHub `gh` adapter, binding, and provider cache (`mb-y1ax`, `mb-jlon`, `mb-p4sw`, `mb-duu7`, `mb-wx32`)

#### Phase 3A: Transport, auth, binding, and snapshot kernel (`mb-y1ax`, `mb-jlon`, `mb-p4sw`, `mb-ji83`, `mb-i3xc`, `mb-2oxp`)

- [ ] Define the provider transport port, then implement only `GitHubGhAdapter` with
  bounded `gh api` REST/GraphQL calls and explicit host selection.
- [ ] Register the adapter through `ProviderAdapterSpec`; reject duplicate
  provider/instance claims, inject only provider-neutral ports, and await cancellation
  and close during root replacement and application shutdown.
- [ ] Route every provider command through the shared no-shell, bounded, cancellable
  subprocess runner (`mb-y1ax`); pass variables as bounded JSON stdin, parse `--include`
  status plus allowlisted headers separately from the body, and cap and sanitize stdin,
  stdout, stderr, environment, and diagnostics before an adapter sees them.
- [ ] Add non-secret auth preflight and typed recovery states for missing `gh`, missing
  login, insufficient scope, permission loss, rate limiting, network failure, and
  cancellation; after preflight, resolve the active principal’s stable opaque ID through
  a bounded fixed `/user` request, keep login/scopes as retrieval observations, and
  never start interactive login on a request path.
- [ ] Add GitHub repository binding without changing generic cache identity.
- [ ] Publish immutable provider-resource snapshots through the `mb-i3xc` store kernel
  behind `ProviderResourceStorePort`: auth-context and query-key pointers, distinct
  transaction and collection states, atomic current plus `last-complete`, reader leases,
  and bounded reachability reclamation.
- [ ] Perform acquisition without locks, then revalidate the entry lease and auth
  context under entry → provider/resource lock order before publication.
- [ ] Publish and inspect `HostedRepository/v1` before any PR acquisition; keep raw API
  responses, credentials, and transport cache entries out of durable state.
- [ ] Add stage-level progress, cancellation, rate-limit observations, and diagnostics
  without turning provider refresh into a generic cache hit.

#### Phase 3B: Directly addressed PR bundle (`mb-h64t`)

- [ ] Fetch a selected `ChangeRequest/v1` frontmatter artifact and its bounded review,
  top-level conversation comment, thread, review-comment, check, and status companions,
  including `Review/v1` artifacts both with and without summary prose and a
  direct-addressed PR absent from the index.
- [ ] Ask core to fetch only the selected base, head, and optional merge refs into a
  Metabrowser namespace; listing PRs fetches no refs.
- [ ] Prove the selected bundle, comparison object IDs, partiality, and typed
  unavailable states are inspectable and reusable offline before an index or nav panel
  exists.

#### Phase 3C: Bounded PR discovery index (`mb-lnkl`)

- [ ] Publish a bounded `ChangeRequestIndex/v1` with explicit query, pages, cursors,
  stable sort/tie-breaker, per-page provenance, first/last observation times, remote
  consistency, completeness, freshness, and truncation; do not use `gh --paginate`,
  `gh --cache`, or durable raw API responses.
- [ ] Keep index summaries separate from selected bundles; listing never fetches PR Git
  refs or hydrates descriptions, reviews, review/check summaries, threads, checks, or
  patches.
- [ ] Let direct hydration supplement an index without requiring the item to match its
  filter, sort, or current bounded window.

### Phase 4: Hosted-review views and virtual PR collection (`mb-r19i`)

#### Phase 4A: Direct PR document and comparison (`mb-xzj3`, `mb-6mle`, `mb-83w0`, `mb-81p5`)

- [ ] Mount plugin-owned browser and resource routes with path parameters and honest
  responses; retain exact data hooks for simple models.
- [ ] Register route-backed `change-request` through `ResourceKindSpec`, then register
  `/hosted/<provider-kind>/<instance-key>/<repository-key>/change-request/<resource-key>`
  through `AddressSpaceSpec` so the same parser, formatter, selection application,
  preview claim, startup, popstate, root-replacement, and disposal lifecycle drives the
  browser and `metab --show`.
- [ ] Render the frontmatter artifact as a directly addressed PR document without an
  index or nav panel: validated title, identity, actors, state, merge/review/check
  summaries, freshness, and the Markdown description.
- [ ] Render the selected PR comparison through the existing Git adapter, File Diff
  Format, and diff plugin; render base/head Markdown through revision content.
- [ ] Show reviews, checks, merge state, partiality, offline state, refresh status, and
  unavailable refs without adding provider fields to File Diff Format.

#### Phase 4B: Pull Requests virtual collection (`mb-uh6p`, `mb-iw1v`)

- [ ] Add the repository-scoped plugin SDK surface (`mb-uh6p`) for virtual nav
  collections, including loading, error, replacement, restoration, and disposal.
- [ ] Register a Pull Requests nav panel backed by the cached index, reusing Git
  history’s bounded paging, virtualization, focus, selection, and restoration patterns.
- [ ] Model the panel root as a virtual folder-like collection and each PR as an
  item-like document plus a folder-like container whose children are changed files.
- [ ] Project commit summaries and PR rows through `RepositoryActivity/v1` when sharing
  history UI mechanics; retain separate Git and provider authorities and do not invent a
  mixed global order when pagination cannot support one.
- [ ] Drive counts and folder visibility from the complete bounded index model, not the
  currently mounted rows.

#### Phase 4C: Anchored review threads (`mb-rldc`)

- [ ] Deliver provider-neutral review threads and diff anchors after direct comparison
  rendering is stable, with explicit outdated, unresolved, and unmappable states.
- [ ] Cover file-level, single-line, and range anchors as a closed tagged union.
  Map only when immutable Git identity and line context are sufficient; otherwise show
  the provider’s original anchor without inventing a current line.

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

### Later sibling: Hosted releases (`mb-7srn`)

Releases are the next proof that the framework is a general external-resource system,
not a PR-only stack.
They remain outside the initial v0.11 PR slice unless the milestone is expanded
explicitly. Each row is one formal stacked pull request; its implementation child is
followed by an independent review/publication child, and `mb-kk47` alone owns
approval-gated landing, retargeting, exact-diff revalidation, and post-merge
verification.

| Formal phase PR | Implementation | Review/publication | Result |
| --- | --- | --- | --- |
| R0 contracts (`mb-g6ed`) | `mb-42j7` | `mb-5m4h` | `Release/v1` frontmatter, `ReleaseAsset/v1` and `ReleaseIndex/v1` pure YAML, profile declarations, corpora, parsers, schemas, and architecture evidence |
| R1 GitHub mapping (`mb-esj2`) | `mb-xj80` | `mb-npdt` | Scrubbed public coverage oracle and fixed bounded `gh api` normalization; every field observed, derived, optional, or unavailable |
| R2 direct cache (`mb-aw0x`) | `mb-nz6a` | `mb-2u4m` | `/releases/tag/<tag>` reduction, one immutable Release plus bounded asset metadata, exact tag revision availability, partial/offline publication, and no implicit asset-byte download |
| R3 direct views (`mb-bbw8`) | `mb-oo4w` | `mb-g74x` | Registered `release` resource kind, generic hosted address, Release and Source views, exact tag revision, asset children, CLI parity, and browserless lifecycle evidence |
| R4 discovery/nav (`mb-fkcs`) | `mb-1742` | `mb-gp0k` | Bounded release index, explicit pagination/completeness, Releases virtual collection, restoration/disposal, and optional activity projection |

`Release/v1` uses `frontmatter-md`: YAML contains provider/repository identity,
canonical URL, tag, exact tag-revision availability, normalized title, optional author,
publication state, release stage, creation time, and optional `released_at`; the
complete release notes are the Markdown body and participate in snapshot identity.
GitHub `published_at` maps to `released_at`. `target_commitish`, generated-note
controls, mutable “latest” status, and other fields without a common consumer stay out
of v1.

`ReleaseAsset/v1` is separate so mutable asset observations do not rewrite release
notes. The detail profile accepts exactly one Release plus `0..N` assets, where the
installed profile declares `N`; an over-bound provider result publishes explicit
partial/truncation evidence rather than growing without limit.
The index profile accepts exactly one ReleaseIndex.
Asset bytes remain an explicit on-demand content workflow.
The direct release path lands before its list and nav panel, matching the direct-PR
sequence.

The release phases are implementation-ready at these file and function seams:

| Phase | Files and functions | Required evidence |
| --- | --- | --- |
| R0 contracts | `builtin_plugins/hosted_releases/release_models.py`: `Release`, `ReleaseAsset`, `ReleaseIndex`; `artifacts.py`: `serialize_release_artifact`, `parse_release_artifact`, `serialize_release_asset_artifact`, `parse_release_asset_artifact`, `serialize_release_index_artifact`, `parse_release_index_artifact`, `release_snapshot_identity`; `contracts.py`; `resource_profiles.py`; `hosted-releases-model.js`: `parseRelease`, `parseReleaseAsset`, `parseReleaseIndex` | Three valid/invalid corpora, Python/browser agreement, schemas, map rows, distribution inventory, bounded `0..N` asset declaration, and proof that `provider_resources` is reused without importing `hosted_review` |
| R1 GitHub mapping | `builtin_plugins/github/release_queries.py`: `build_release_detail_request`, `build_release_assets_request`; `release_mapping.py`: `map_github_release`, `map_github_release_asset`, `map_github_release_row` | Fixed bounded detail/asset `gh api` inputs, scrubbed detail/asset/index-row oracle, null/error coverage, and every field classified observed, derived, optional, or unavailable; R4 owns the list request that consumes the row mapper |
| R2 direct cache | `builtin_plugins/github/urls.py`: `reduce_github_url`, `parse_github_release_selection`; `builtin_plugins/hosted_releases/service.py`: `get_release`, `refresh_release`; `plugin_loader/provider_addresses.py`: `format_hosted_address` | Stable object-ID resolution from a typed tag locator, auth-scoped current/last-complete, exact observed tag OID, bounded asset metadata, offline/partial tests, and no implicit asset-byte fetch |
| R3 direct view | `builtin_plugins/hosted_releases/routes.py`: `release_resource`, `release_asset_resource`, `hosted_resource_shell`; `hosted-releases-view.js`: `prepareReleaseView`, `mountReleaseView`, `disposeReleaseView`; manifest/index/styles | Registered resource kind, Release and Source views, item/container children, text-safe metadata, untrusted Markdown, exact tag revision, CLI parity, production-JavaScript lifecycle golden, and distribution evidence |
| R4 discovery/nav | `builtin_plugins/github/release_queries.py`: `build_release_index_request`; `builtin_plugins/hosted_releases/service.py`: `list_releases`, `refresh_release_index`; `hosted-releases-panel.js`: `createReleasesPanel`, `loadIndexPage`, `openRelease`, `restoreReleaseSelection`, `replaceRoot`, `dispose` | The bounded list request consumes R1’s `map_github_release_row`; query identity, pagination, truncation, offline behavior, bounded counts, virtual-list restoration/replacement/disposal, CLI golden, browserless golden, parity rows, and distribution checks |

### Later provider: GitLab (`mb-51uj`)

- [ ] Implement the same provider port for GitLab merge requests, discussions,
  pipelines, auth, pagination, and selected refs after the GitHub-first format and views
  have shipped.
- [ ] Add only fields observed from that adapter and only provider-specific companion
  records with named consumers; do not widen v0.11.0 contracts speculatively.

## Incremental Shipping Map

| Slice | Depends on | Mergeable result |
| --- | --- | --- |
| v0.11 start (`mb-xxhi`) | v0.10.0 release `mb-i57d` | Implementation branch starts from the released `main` commit |
| Hosted Review 0A (`mb-u8n8` through `mb-c08x`) | Released v0.10.0 baseline and design PR | Dormant pre-schema ChangeRequest models, typed frontmatter codec, portable Python/browser corpus, and installed-artifact proof |
| Hosted Review 0B (`mb-pnz5`, `mb-915y`, `mb-rla6`) | Exact head of the preceding formal phase pull request | One pull request per no-network phase for provider storage, repository, review, signal, activity records, and the scrubbed GitHub coverage oracle; each is retargeted and revalidated when its base lands |
| Hosted Review 0C (`mb-lqae`, `mb-dhz8`) | Phase 0B and SoftSchema selection `mb-4gnu` | Compiled enforced schemas, installed host registry, complete inventory, distribution, and parity gate; closes `mb-63ym` |
| Generic cache | Cache Phase 1A/1B beads | Any supported repository source is pinned and reusable offline |
| GitHub URL reducer (`mb-12cz`, `mb-ew38`) | Generic cache | Any supported GitHub repository URL opens without the GitHub API |
| Branch materialization (`mb-z335`, `mb-2xq7`) | Repository URL open | Any exposed and authorized branch opens without moving the pinned root |
| GitHub transport and repository summary (`mb-y1ax`, `mb-p4sw`, `mb-ji83`, `mb-i3xc`, `mb-2oxp`) | Format, generic jobs, owner-only cache | Auth, adapter lifecycle, snapshot kernel, and one offline repository summary |
| Direct PR cache (`mb-h64t`) | Transport, summary, selected refs | Any directly addressed and authorized PR has one reusable bundle |
| Direct PR view (`mb-xzj3`, `mb-6mle`, `mb-83w0`, `mb-81p5`) | Direct PR cache, trust profile | One GitHub PR URL opens its registered common document and full comparison offline through the generic hosted address |
| PR index (`mb-lnkl`) | Direct PR cache | A bounded discovery cache lists PR summaries without fetching refs |
| PR nav (`mb-uh6p`, `mb-iw1v`) | Direct PR view, index | Pull Requests appears as a virtual repository collection |
| Review anchors (`mb-rldc`) | Direct PR comparison | Threads render at honest current, outdated, or unresolved locations |
| Hosted releases R0-R4 (`mb-7srn`) | Contract/profile/resource-kind registries and GitHub provider store | One direct release works before a bounded Releases collection; each release phase is a separately reviewed formal PR |

The direct-PR path intentionally crosses Phase 4A before Phase 3C is needed by a user
surface. This is not a dependency inversion: the index and direct bundle are sibling
cache products. It lets the smallest complete workflow ship and be tested before
discovery UI increases acquisition and browser scope.

## Testing Strategy

- **Hosted-review contracts:** every valid frontmatter and pure-YAML fixture passes
  structural and semantic validation in producer and consumer implementations; invalid
  fixtures fail with stable codes and paths; unknown provider enum values normalize
  without opening the record schema; no common contract contains a GitHub-only field.
- **Installed registries:** unknown, duplicate, incomplete, or conflicting contract,
  resource-profile, resource-kind, and view declarations fail; cached data cannot
  provide a declaration; a synthetic release-index profile validates and closes over
  generic retrieval evidence without adding a storage target variant.
  The generic format inventory checks every installed contract and profile against its
  packaged evidence and maintained architecture row without a built-in ID allowlist.
- **Frontmatter artifacts:** complete PR descriptions, top-level comments, and review
  comments round-trip as Markdown bodies; structured consumers read only YAML; hostile
  fences and Markdown remain bounded and untrusted; and snapshot identity changes when
  either authoritative metadata or the body changes.
- **Coverage oracle:** every modeled field is present in at least one recorded, scrubbed
  response, or is explicitly marked deterministically derived, Metabrowser-owned, or
  optional/unavailable.
- **Provider snapshots:** only structurally valid committed manifests move `current`;
  valid partial collections remain visibly partial while `last-complete` stays readable;
  failed transactions leave pointers unchanged; authorization contexts, tombstone proof,
  deletion, permission loss, not-requested, and rate-limit outcomes remain distinct.
- **PR index:** exact query-key pointers, configured bounds, stable ordering, per-page
  provenance, pagination cursors, remote consistency, freshness, and completeness are
  visible; rows contain no review/check summaries; list acquisition fetches no PR refs;
  a direct PR URL works without a warm or complete index; raw provider responses never
  become durable authority.
- **Adapter and auth:** fixtures cover fixed REST and GraphQL mappings, `--include`
  parsing, JSON stdin, GraphQL data-with-errors and nulls, GitHub Enterprise version
  support, missing CLI/login/scope, permission loss, rate limits, cancellation,
  malformed output, and output bounds without exposing a credential; no test uses an
  interactive login, field flags, verbose output, or `gh --paginate`.
- **Relationships:** all references resolve within a manifest or carry an explicit
  unavailable state; stack cycles and missing members are reported, not repaired by
  guessing.
- **Views:** every browser-consumed record passes its packaged validator; hostile
  provider strings are inserted as text or untrusted Markdown; provider links are
  HTTPS-only; loading, stale, partial, unavailable, and offline states each render
  distinctly; incomplete-collection indicators survive; file, line, and range anchors
  that cannot be mapped show as outdated rather than pointing at an invented line.
- **Navigation:** a cached PR index populates the virtual Pull Requests collection;
  paging and virtualization do not change counts or folder visibility; selecting a row
  opens its hosted-review document; expanding it exposes the same changed-file views as
  any other comparison.
- **Parity:** repository and PR routes, records, auth/query-scoped pointers, URL
  reduction, address lifecycle, direct-view lifecycle, panel window/selection/
  restoration, root replacement, and disposal each receive an architecture-map row and
  the exact `tests/dom/hosted-review-session.js` production-path golden.
- **Distribution:** the installed wheel and source distribution contain every registered
  model, compiled schema, plugin asset, and format inventory.
  Both isolated-install smokes derive this set from installed capabilities rather than a
  second hard-coded contract list.
  `make verify` remains the handoff gate.

## Rollout and Compatibility

Hosted Review Format and provider-store contracts in this plan are unreleased.
Plugin SDK 0.6, by contrast, is the v0.10.0 public baseline.
Artifact contracts and resource profiles use the new, separately versioned
`metabrowser.capabilities.v1` installed-Python extension surface; changing its contract
requires a new entry-point group version, not a browser SDK compatibility shim.
The planned router, address-space, reducer, provider-adapter, and nav-panel declarations
may remain optional additive SDK 0.6 capabilities only while every existing manifest and
`window.metabrowser` call keeps its signature and behavior; their implementation must
update plugin-author documentation and `CHANGELOG.md`. Any changed existing signature or
semantic contract bumps `PLUGIN_SDK_VERSION` and all built-in manifests in the same
commit, with no dual compatibility layer.

Once released, provider reclamation preserves `current`, `last-complete`, one diagnostic
predecessor, explicit archival pins, and any reader-leased snapshot regardless of
whether the source can be reacquired.
Older unreachable generations remain safely reclaimable even when the source is offline
or deleted; the last validated reachable observation is never automatically removed.

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
