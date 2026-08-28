# Feature: GitHub Provider — Content Model, Acquisition, and Pull Requests

**Date:** 2026-08-27

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Vision

Once a repository is in the local cache, Git already answers most questions about it:
history, revisions, diffs, and file content all work through the shipped pipeline.
What Git cannot answer is what happened *around* the code — the pull request that
proposed a change, the review that argued about it, the checks that gated it.

This plan adds that layer, and only that layer.
It reads GitHub, normalizes it into strict versioned records, stores them as immutable
snapshots beside the cached repository, and renders them through views that resolve
every piece of code content back to Git object ids.

Git stays authoritative for content, history, and diffs.
Provider records describe hosted state and *refer to* immutable Git object ids; they
never replace the object database.
A pull-request comparison is a Git comparison with provider context layered around it,
which is why it reuses the existing File Diff Format pipeline rather than introducing a
second one.

## Why this is a separate plan

This work was Phases 4 through 7 of the
[repository-library plan](plan-2026-08-11-open-repo-from-git-url.md).
It moved here because the two have diverged in every dimension that matters for
planning:

- **Different dependencies.** The generic cache is gated on the content-trust chain and
  on the Git-status clean predicate.
  This plan is gated on the cache existing and on nothing else.
- **Different risk.** The cache is filesystem and format work whose failure modes are
  local and recoverable.
  This is network, authentication, rate-limit, and pagination work whose failure modes
  are partial and remote.
- **Different priority.** They are now scheduled independently, and a single document
  meant the generic cache contract was re-reviewed every time the provider model moved.

The repository-library plan keeps the generic phases: format foundation, acquisition and
URL opening, catalog and refresh, the chooser, and large-repository support.

## What this plan needs from the cache

Named precisely, because the dependency was previously stated as “Phase 2 job/storage
primitives”, which is broader than what is actually required.

| Needed | Why | Where it lives |
| --- | --- | --- |
| A published cache entry with a stable identity | Provider records hang off a repository that already exists locally | Repository library Phase 1B |
| Atomic publication and no-replace rename | Snapshot sets and manifests need the same publication guarantee the cache uses | Repository library Phase 1A |
| Application-home locking | Provider refresh must not race generic refresh on one entry | Repository library Phase 1A |
| Job progress, cancellation, and stage outcomes | A provider refresh is a long multi-stage operation that must report per-stage results | Repository library Phase 2 |
| Core Git ref fetching on request | Pull-request heads live in refs the plugin asks core to fetch; the plugin never runs Git | Repository library Phase 2 |

The catalog, the chooser, purge, and size accounting are **not** prerequisites.
If scheduling requires it, the two rows attributed to repository-library Phase 2 are a
small extraction — the job lifecycle and ref fetching — and can be delivered ahead of
the rest of that phase.

## GitHub Browsing Content Model v1

“Full GitHub content model” is bounded here to the read-only repository-browsing domain.
GitHub exposes many administrative and product APIs that do not contribute to browsing
source, issues, or code review.
Claiming to model all of them would leave the phase with no completion criterion.

Phase 1 models the complete v1 browsing set before Phase 2 performs an API request.
It lands Pydantic models, compiled SoftSchema contracts, field documentation, normalized
fixtures, invalid fixtures, relationship tests, and a format inventory.
No renderer reads a provider record that the inventory does not register.

### The corpus needs a coverage oracle, not just fixtures

Writing the model before the adapter is the right order, and the reason is in the
[design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md):
if the first fixture corpus comes from one API query, that response shape becomes the
model. Hand-authored normalized fixtures avoid that.

They also cannot answer a different question.
A fixture proves the model is self-consistent and that validation rejects what it
should. It cannot prove that GitHub actually supplies a modeled field, or supplies it
over the transport Phase 5 chooses.
Nothing in a hand-written corpus fails when a field turns out to be unobtainable, so the
discovery lands in Phase 5, after roughly sixteen contracts and their fixtures are
frozen.

Phase 1 therefore validates its inventory against a small set of **recorded, scrubbed**
real responses, used only as a coverage oracle:

- captured once, from public repositories, with tokens, rate-limit headers, and volatile
  transport metadata removed;
- kept outside the fixture corpus and never loaded by a renderer, an adapter, or a
  contract test — it is not authoritative and does not become a second model; and
- consumed by exactly one check, which asserts that every field in the contract
  inventory is present in at least one recorded response, and reports the transport that
  supplied it.

A field that no recorded response supplies is not automatically wrong — it may be
derived, or intentionally Metabrowser-owned like `PullRequestStack/v1`. It just has to
be labeled as such deliberately rather than by omission.

This keeps the review’s ordering (the model leads) while removing its blind spot (the
model is unfalsifiable until Phase 5).

### Transport is already partly decided, and the model should say so

The example below records `review_decision` and `counts.reviews`. Both are GraphQL
fields with no REST equivalent — REST returns neither a review decision nor a review
count — so the browsing model as written presumes GraphQL as the primary source for pull
requests, with REST filling gaps.

That is a reasonable choice and it is not what
[Decisions Deferred to Their Evidence Phase](#decisions-deferred-to-their-evidence-phase)
currently claims. What remains open for Phase 5 is which transport serves each
*acquisition*, and that stays open.
What is already settled is that some modeled fields are GraphQL-only, and the durable
record still must not expose that.
Phase 1 marks each such field so the constraint is visible: either the field is
obtainable and the oracle proves it, or it is optional with an explicit `not_requested`
state rather than a hole discovered during adapter work.

### Record families

| Family | Contracts | Purpose |
| --- | --- | --- |
| Provider storage | `ProviderBinding/v1`, `Retrieval/v1`, `SyncManifest/v1`, `ResourceSet/v1`, `Tombstone/v1` | Bind the generic entry to a stable GitHub repository, describe acquisition, and publish complete snapshot sets |
| Repository | `GitHubRepository/v1` | Stable provider identity, owner/name, URLs, visibility, default branch, and provider timestamps |
| Work items | `GitHubIssue/v1`, `GitHubIssueComment/v1`, `GitHubTimelineEvent/v1` | Issues and their bounded discussion and state history |
| Pull requests | `GitHubPullRequest/v1`, `GitHubPullRequestReview/v1`, `GitHubReviewThread/v1`, `GitHubReviewComment/v1` | Review state, Git endpoints, decisions, threads, and line anchors |
| Commit signals | `GitHubCheckSuite/v1`, `GitHubCheckRun/v1`, `GitHubCommitStatus/v1` | Mutable provider conclusions attached to an immutable commit ID |
| Derived relationships | `PullRequestStack/v1` | Explicit, provenance-bearing dependency edges and display order; never presented as a native GitHub object |

Small values such as `ActorRef`, `RepositoryRef`, `Label`, `MilestoneRef`,
`GitObjectRef`, and `CollectionState` are nested `$defs`, not independently refreshed
files. An actor reference carries enough identity and display information to render when
no full actor resource was fetched.

Issue and pull-request records are separate closed contracts.
A pull request is not also written as an issue record, so common provider fields do not
acquire two authorities.
Shared code may project either type into an in-memory work-item summary.
It does not use an open union or an untyped `data` mapping on disk.

### Identity and Git references

Every provider object stores the stable GitHub node ID when available, its repository
ID, its human URL, and its repository-local number where applicable.
File paths use a safe digest or encoded resource key; the full provider ID inside the
record is authoritative.
Repository renames change display coordinates, not provider identity or generic cache
identity.

Pull requests record:

- stable pull-request and repository IDs, number, URL, title, body, author, state,
  draft/locked flags, provider timestamps, labels, assignees, milestone, and review
  decision;
- base and head repository IDs, ref names, and full Git object IDs;
- an optional merge object ID and its observation state;
- requested reviewers and teams as bounded references; and
- provider-reported aggregate counts where GitHub exposes them without fetching a
  collection.

The proposed strict core is concrete enough to fixture before acquisition work:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.github:GitHubPullRequest/v1
  envelope: pull_request
  status: enforced
pull_request:
  id: PR_kwDOExample
  repository_id: R_kgDOExample
  number: 123
  url: https://github.com/example/project/pull/123
  title: Add repository caching
  body: ""
  author:
    id: U_kgDOExample
    login: octocat
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
  requested_reviewers: []
  requested_teams: []
  review_decision: review_required
  counts:
    commits: 4
    issue_comments: 2
    reviews: 1
```

Phase 1 freezes the exact field set and enum policy from representative fixtures.
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

Provider `created_at` and `updated_at` describe the GitHub object.
Retrieval time, transport, API version, query identity, HTTP validators, rate-limit
observation, and normalization version belong to retrieval metadata.
This prevents a conditional HTTP detail from becoming part of the domain object’s
identity.

A confirmed deletion receives a tombstone.
Authentication failure, permission loss, rate limiting, and a resource never fetched are
distinct states. Refresh does not turn any of them into deletion.

### Stacked pull requests

GitHub does not provide one universal stacked-pull-request object.
`PullRequestStack/v1` is a Metabrowser projection over pull requests and Git history.
It contains:

- the ordered member pull-request IDs;
- directed edges with a controlled relation such as `depends_on`;
- the evidence for each edge, such as base/head topology, explicit user metadata, or a
  named tool adapter;
- derivation algorithm and version;
- observation time and source snapshot IDs; and
- conflicts, cycles, missing members, and confidence where the evidence is not
  definitive.

The model never silently treats numbering, creation time, or adjacent branches as a
dependency. Phase 1 defines and fixtures the record.
Phase 4 implements derivation and navigation after ordinary PR snapshots and views are
stable.

## Provider Snapshot Storage

GitHub records are mutable observations, but cache publication should still be atomic
and old data should remain readable during refresh.
The provider directory begins in Phase 2:

```text
<entry>/providers/github/
├── binding.yml
├── objects/
│   └── <kind>/
│       └── <resource-key>/
│           └── <snapshot-id>.yml
├── manifests/
│   └── <sync-id>.yml
└── views/
    ├── repository/current.yml
    ├── issues/<number>/current.yml
    └── pull-requests/<number>/current.yml
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

The physical layout remains an implementation hypothesis until Phase 1 fixtures measure
path length, object counts, YAML size, parse time, and snapshot duplication.
The invariants are fixed: immutable snapshots, atomic current manifests, strict
contracts, safe path keys, explicit completeness, and no cross-entry writes.
If measurement favors a sharded or indexed equivalent, the architecture map and layout
format must say so before Phase 2 writes released data.

Raw API responses are not authoritative and are not stored by default.
A future bounded diagnostic capture, if justified, belongs under a separate
content-addressed namespace, removes secrets and volatile headers, and has an explicit
retention policy.

## GitHub Acquisition Boundary

Phase 2 adds a built-in GitHub plugin after the model phase.
It maps REST or GraphQL responses into transport-neutral records; the durable schema
does not expose response shape, pagination syntax, or client-library types.

The provider binding resolves a generic cache entry to a stable GitHub repository ID
without changing the cache source digest.
Credentials remain in `gh`, the operating system credential store, or another explicit
provider adapter. The plugin reports which credential source it used but never reads a
secret into a cache record.

Initial acquisition is on demand:

- repository summary for the repository tab;
- one issue bundle when an issue URL or chooser selection requests it; and
- one pull-request bundle, including the bounded collections needed by the first PR
  view.

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

## Phased Implementation Plan

### Phase 1: Browsing model and schema corpus — no network

- [ ] Write the contract inventory in this plan as Pydantic models and deterministic
  compiled schemas, using simple closed objects and local `$defs`.
- [ ] Define stable IDs, repository refs, Git object refs, provider timestamps,
  retrieval metadata, completeness, pagination, tombstones, and unknown enum handling.
- [ ] Define issue, PR, review, thread, comment, check, status, timeline, and stack
  relationships without an opaque payload field or raw API authority.
- [ ] Build representative normalized fixtures for open, closed, merged, draft, forked,
  deleted, inaccessible, partial, paginated, outdated-anchor, unknown-enum, and stacked
  cases.
- [ ] Capture the scrubbed recorded-response oracle and add the check that every modeled
  field is either present in a recorded response, or explicitly marked derived or
  optional with a `not_requested` state.
- [ ] Measure the proposed immutable-object and atomic-manifest layout; freeze or revise
  it before released provider data is written.
- [ ] Register every record and view surface in the architecture map and add an
  inventory test that fails when a contract lacks a producer, consumer, schema, or
  fixture.

### Phase 2: Binding, acquisition, and provider cache

- [ ] Add the provider storage interface, namespace allocation, immutable snapshot
  writer, sync manifest, and atomic current pointers.
- [ ] Add GitHub repository binding without changing generic cache identity.
- [ ] Map bounded REST or GraphQL responses into the Phase 1 contracts; support
  conditional requests, cursors, rate limits, tombstones, and partial outcomes.
- [ ] Fetch repository, selected issue, and selected PR bundles on demand; keep the last
  completed manifest readable on refresh failure.
- [ ] Ask core to fetch selected provider refs, and record availability for every Git
  object reference.
- [ ] Add refresh controls and stage-level diagnostics without making provider refresh
  part of a generic cache hit.

### Phase 3: Repository, issue, and pull-request views

- [ ] Add plugin-owned repository and issue views with explicit loading, stale, partial,
  unavailable, offline, and refresh states.
- [ ] Render PR comparisons through the existing Git adapter, File Diff Format, and diff
  plugin.
- [ ] Layer title, author, state, checks, reviews, threads, and freshness around the Git
  comparison; preserve incomplete-collection indicators.
- [ ] Render changed Markdown at the PR head through the existing revision-content path.
- [ ] Map review anchors only when their Git identity and line context are sufficient;
  otherwise show the original anchor as outdated or unresolved.

### Phase 4: Stacked pull requests and cross-object projections

- [ ] Implement stack derivation against the Phase 1 contract with explicit evidence,
  algorithm version, conflicts, and cycles.
- [ ] Add adapter points for explicit stack metadata without hard-coding a third-party
  tool into core or treating heuristics as fact.
- [ ] Add stack navigation, aggregate status, and adjacent comparisons as derived views
  over immutable PR and Git snapshots.
- [ ] Recompute projections when any input snapshot changes; never mutate source PR
  records to store derived order.

## Testing Strategy

- **Provider contracts:** every valid fixture passes structural and semantic validation;
  every invalid fixture fails with a stable code and path; unknown provider enum values
  normalize without opening the record schema.
- **Coverage oracle:** every modeled field is present in at least one recorded, scrubbed
  response, or is explicitly marked derived or optional with a `not_requested` state.
- **Provider snapshots:** multi-page and partial refreshes publish only complete
  manifests; a failed refresh leaves the old current set; deletion, permission loss,
  not-requested, and rate-limit outcomes remain distinct.
- **Relationships:** all references resolve within a manifest or carry an explicit
  unavailable state; stack cycles and missing members are reported, not repaired by
  guessing.
- **Views:** loading, stale, partial, unavailable, and offline states each render
  distinctly; incomplete-collection indicators survive; a review anchor that cannot be
  mapped shows as outdated rather than pointing at an invented line.
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
- [File Diff Format v1](../../architecture/file-diff-format/file-diff-format.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
