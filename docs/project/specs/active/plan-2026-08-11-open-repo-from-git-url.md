# Feature: Repository Library and Open from a Git URL

**Date:** 2026-08-11 (rewritten 2026-08-26)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Vision

Metabrowser should open a remote repository as easily as a local directory:

```shell
metab https://github.com/pallets/flask
```

The first open acquires the repository into a versioned application cache.
Later opens reuse a pinned, read-only working tree immediately, without consulting the
network. The cache becomes a local repository library: durable enough to make commonly
opened repositories feel local, but recoverable from its source when an entry is
damaged.

The initial product slice is deliberately provider-neutral.
A GitHub clone URL is an ordinary Git source in this phase.
Opening it must not require the GitHub API, a GitHub account, provider detection, or a
GitHub-specific record.
That boundary lets basic cache support land and prove itself before provider metadata
expands the system.

Later phases add generic cache operations and a repository chooser.
GitHub support then starts with a separate content-model phase: strict, versioned
records for repositories, issues, pull requests, reviews, checks, comments, and derived
pull-request stacks.
Only after those contracts and a representative fixture corpus are accepted does an API
adapter write them or a view consume them.

Git remains authoritative for repository content, history, and diffs.
Provider records describe hosted state and refer to immutable Git object IDs; they do
not replace the object database.

The
[repository-cache research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
contains the acquisition measurements and prior-art survey.
Its 2026-08-26 addendum separates dated evidence from the current design after Git diff
and revision navigation shipped through v0.8.0. The
[design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
records the changes that produced this phased plan.

## Release Principle

Each phase below is an independently reviewable pull request or a short sequence of pull
requests with one acceptance boundary.
In particular:

- The format foundation can land without cloning a repository.
- The generic Git cache can land without catalog UI or GitHub code.
- GitHub schemas can land with fixtures and validation before any network acquisition.
- GitHub acquisition can land before provider-specific views.
- Derived stack navigation can land after ordinary pull-request reading is stable.

No phase reserves an opaque extension object for work that has not been modeled.
A later record family receives its own contract, storage path, producer, consumer, and
invalidating tests.

## Goals

- Accept repository-root HTTPS and SSH clone URLs anywhere the CLI currently accepts a
  root path.
- Preserve the root argument as a string at the Click/Typer boundary, then classify it
  before any `Path` construction can rewrite URL syntax.
- Derive one stable cache identity from the credential-free clone source, and reuse the
  same entry on every later open.
- Publish repositories under `~/.metabrowser/cache/repos/<uniquified-slug>/gitroot` only
  after checkout and metadata validation complete.
- Keep the browsed working tree pinned and read-only from Metabrowser’s perspective.
  Fetching refs must not dirty or silently advance it.
- Make a cache hit an offline operation.
  Network work begins only for a missing entry or an explicit refresh.
- Establish `~/.metabrowser/` as a versioned application home beginning at layout format
  `f01`.
- Give each machine-owned YAML family a strict, independently versioned contract, with
  deterministic compiled schemas and golden fixtures.
- Make provider storage additive.
  Generic acquisition, identity, refresh, and purge do not depend on GitHub.
- Model the GitHub browsing domain before fetching it, including stable identities,
  provenance, completeness, pagination, tombstones, and Git object references.
- Reuse the shipped Git history, revision, and File Diff Format paths.
  Cached content must behave like the same repository opened from a user-managed
  directory.
- Keep credentials in existing Git and provider credential stores.
  No persistent record, log, diagnostic, or browser response may contain a token or
  credential-bearing URL.

## Non-Goals

- Editing a cached working tree.
  URL-opened cache roots never receive file-mutation capabilities.
- Automatically advancing a live checkout when a remote ref moves.
  Fetch, select, and promote are distinct operations.
- Requiring provider support for the first usable cache.
  GitHub is not on the Phase 1B critical path.
- Mirroring every GitHub API. The first provider model covers repository browsing and
  review. Organization administration, Projects, Actions logs, packages, billing,
  security alerts, and other account surfaces are outside its v1 scope.
- Using raw GitHub REST or GraphQL responses as the durable application model.
- Writing to GitHub. Provider support remains read-only through the phases in this plan.
- Storing provider credentials in `config.yml`, repository records, or provider
  snapshots.
- Treating a repository’s own `.metabrowser/` directory as trusted configuration.
  Everything under `gitroot` is untrusted repository content.
- Automatic LRU eviction before measurements establish a size and age policy.
  Explicit inspection and recoverable purge come first.
- Supporting arbitrary Git transports.
  Production initially permits HTTPS and SSH; helpers such as `ext::`, the
  unauthenticated `git://` protocol, and local transport overrides remain disabled.

## Current Foundation and Dependencies

As of v0.8.0:

- `metabrowser.git.process` is the only Git subprocess path.
  It already provides fixed arguments, bounded output, timeouts, concurrent stream
  draining, cancellation cleanup, repository-environment scrubbing, and typed failures.
- `/api/git/log`, direct revision routes, commit detail, and Git-backed comparisons use
  full object IDs and can operate against a cached checkout without new content models.
- The diff plugin renders File Diff Format rather than a provider response.
  A future PR view can therefore resolve provider refs to object IDs and reuse the same
  pipeline.
- URL-opened roots remain gated on the untrusted capability profile tracked by
  `mb-vib1`. Cache storage and clone components may land before that gate; serving
  fetched content may not.
- Metabrowser already depends on Pydantic, JSON Schema, ruamel.yaml, PyYAML, and
  frontmatter-format. SoftSchema v0.7.0 is a first-party package over the same boundary,
  but adopting it also raises the frontmatter-format minimum from 0.3 to 0.4. Phase 1A
  must review that upgrade, update `uv.lock`, and run the full supply-chain and
  distribution gates rather than treating the overlap as proof of compatibility.

The v0.8.0 revision click starts a comparison that needs blobs.
Blobless clone followed by background backfill remains the leading acquisition strategy,
but Phase 0 must remeasure the complete current route before promising a timing or
selecting a threshold between full and blobless acquisition.

## Ownership and Layering

The application home has four distinct ownership classes:

| Surface | Owner | Mutability | Recovery rule |
| --- | --- | --- | --- |
| `config.yml` | User and application migration code | Durable and editable | Migrate losslessly; never discard unknown user settings |
| Cache layout and repository identity | Core cache service | Rare writes | Validate, migrate if released data requires it, otherwise quarantine |
| Git object database and `gitroot` | Core Git cache service | Objects and refs may grow; checkout stays pinned | Reacquire or rebuild outside a live entry |
| Provider snapshots and manifests | Provider plugin through core storage APIs | Refreshable | Keep complete snapshots; invalidate or refetch by contract |

Core owns application-home resolution, atomic file publication, locks, safe cache paths,
repository acquisition, Git refresh, and provider namespace allocation.
Provider plugins own their schemas, API adapters, normalized records, routes, renderers,
and styles. Core does not import a GitHub schema or branch on a GitHub object kind.

## Application Home and Cache Layout `f01`

The first released layout is:

```text
~/.metabrowser/
├── config.yml
└── cache/
    ├── layout.yml
    ├── locks/
    ├── staging/
    ├── trash/
    └── repos/
        └── <uniquified-slug>/
            ├── repository.yml
            ├── state.yml
            └── gitroot/
```

Provider directories do not appear in the initial cache implementation.
A later phase may add `<entry>/providers/<provider-name>/` without changing the meaning
of `repository.yml`, `state.yml`, or `gitroot`.

`METABROWSER_HOME` overrides the application home for tests and advanced operation.
If the existing cache-root override is retained, startup rejects a combination that
would split the config and cache authorities.
Paths in config expand a leading `~` against the operator’s home and resolve relative
paths against the application home.
Config parsing never performs shell expansion or evaluates environment syntax stored in
YAML.

### Layout format versus record contracts

The `f01` marker and SoftSchema contract versions solve different problems:

- `f01` names application-home directory semantics and migration order.
- A contract such as `com.github.jlevy.metabrowser.cache:RepositoryIdentity/v1` names
  one YAML payload shape.
- A provider-record change does not force an application-home migration when the old
  provider cache can be retained, converted under a released-data obligation, or
  refreshed.
- A directory or publication-semantics change increments the home format even if every
  individual YAML payload is unchanged.

One module owns `CURRENT_FORMAT`, ordered format history, migration functions, and the
standard future-format error.
Migration holds the application-home lock and publishes `config.yml` last.
An older client that sees a future layout fails before writing.

`config.yml` is user-owned and begins with:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.config:ApplicationConfig/v1
  envelope: config
  status: permissive
config:
  format: f01
  written_by: 0.9.0
  upgrades:
    - version: 0.9.0
      at: "2026-08-26T00:00:00Z"
  cache:
    root: ~/.metabrowser/cache
    refresh: manual
```

The version is illustrative; the implementation writes its actual release.
Config is `permissive` because a compatible older client must preserve unknown user
settings. Known fields still validate.
Credentials are forbidden.

`cache/layout.yml` is machine-owned and `enforced`:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:CacheLayout/v1
  envelope: layout
  status: enforced
layout:
  format: f01
  created_by: 0.9.0
```

The cache is recoverable, but migration does not delete it by default.
A source may be offline or gone.
Unknown and damaged entries move to quarantine or recoverable trash with a diagnostic
that names the retained path.

## SoftSchema Contract Policy

SoftSchema v0.7.0 is the proposed record boundary.
The reviewed source is `jlevy/softschema` release `v0.7.0`; later commits on its `main`
branch are documentation only at the time of this design review.
Runtime adoption uses a released package and a committed lock, not a Git checkout.

### Artifact profile and binding

All cache records use SoftSchema’s `pure-yaml` profile.
Each file carries `contract`, `envelope`, and `status`. It omits `softschema.schema`
deliberately. The application registry binds the contract ID to the schema packaged in
the installed Metabrowser wheel; an untrusted cache file cannot redirect validation to
another path.

Machine-owned records begin at `status: enforced`, not `soft` or `permissive`, because
Metabrowser is their only producer and the schema phase supplies fixtures before a
writer ships. An enforced contract always has both:

- a strict Pydantic model for semantic validation; and
- a deterministic Draft 2020-12 compiled schema for portable structural validation.

Model-only validation is insufficient: an enforced boundary without a compiled schema
can silently accept undeclared fields.
CI compiles every model with `--check`, validates the artifact corpus, verifies the
embedded schema hash, and inspects the installed wheel for every registered schema.

### Schema construction rules

Provider records favor simple, closed objects.
Shared leaf models may compile to local `$defs`, but contracts do not use
inheritance-shaped `allOf` trees or external schema references merely to remove
repetition. That keeps undeclared-property enforcement within SoftSchema’s measured
support matrix and keeps every artifact valid offline.

Transport and provider enums can grow without notice.
A strict record maps an unknown provider value to a documented `unknown` variant and
retains the original string in a bounded `provider_value` field where diagnosis requires
it. It does not reject a whole refresh because GitHub introduced a new timeline event.

Dates and timestamps are RFC 3339 strings with explicit semantic validators.
Git object IDs are lowercase hexadecimal strings paired with the repository object
format where the context does not already establish it.
Integers remain inside the cross-runtime safe range.

### Contract evolution

A contract ID maps to one compiled-schema digest in the repository.
Metabrowser does not silently change the structural accept set behind an existing ID. A
structural change that an older enforced reader could reject receives a new contract
version, even when the new field is optional.
This is stricter than SoftSchema’s general guidance and is intentional for a cache
shared across application upgrades and downgrades.

Semantic clarification that leaves the compiled schema byte-identical may keep the
contract ID only when tests show every released producer and consumer remains valid.
Once a cache contract ships, its migration or invalidation decision names the released
data that requires compatibility.
Before `f01` ships, no speculative legacy reader is added.

Provider snapshots are reacquirable, so a new writer normally leaves old immutable
snapshots untouched and publishes a new manifest under the new contracts.
Core repository identity and user config need a migration or a precise repair path
because they may be the only durable link to an unavailable source.

## Generic Repository Identity and Records

### Source identity

The cache key is a SHA-256 digest of a credential-free source identity.
The directory combines a readable slug with a short digest:

```text
github-com--pallets--flask--7d5c1a2e4b90
```

The full digest in `repository.yml` is authoritative.
If a path already contains a different digest, derivation extends the suffix
deterministically. Claim and publication use no-replace semantics, so concurrent sources
cannot alias or overwrite one another.

Generic normalization is intentionally conservative.
It lowercases the URL scheme and DNS host, removes a default port, and normalizes only
URL syntax whose equivalence is defined by the relevant URI rules.
It preserves path case, a terminal `.git`, SSH versus HTTPS spelling, and other
distinctions a generic Git host may interpret.
Phase 1B rejects fragments, query strings, embedded credentials, control characters, and
ambiguous option-like inputs rather than guessing whether they are presentation syntax
or secrets.

GitHub repository-root HTTPS URLs already work as clone URLs and receive no special
canonicalization. A later GitHub binding may record proven aliases without changing or
merging the generic cache identity.
Automatic entry merging is out of scope because it could discard one separately acquired
source.

### Stable identity and mutable state are separate

`repository.yml` is written during publication and does not change during ordinary open
or refresh:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:RepositoryIdentity/v1
  envelope: repository
  status: enforced
repository:
  id: sha256:<full-source-identity-digest>
  slug: github-com--pallets--flask--7d5c1a2e4b90
  source:
    display_url: https://github.com/pallets/flask
    clone_url: https://github.com/pallets/flask
    transport: https
  created_at: "<RFC-3339 timestamp>"
  acquisition:
    strategy: blobless
    git_version: "<version>"
    object_format: sha1
```

`state.yml` contains mutable cache state and is atomically replaced:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:RepositoryState/v1
  envelope: state
  status: enforced
state:
  active_revision: <full-object-id>
  default_remote_ref: refs/remotes/origin/main
  object_state: backfilling
  last_opened_at: "<RFC-3339 timestamp>"
  last_fetch_at: null
  pending_revision: null
  last_operation:
    kind: acquire
    outcome: succeeded
    at: "<RFC-3339 timestamp>"
```

Separating the files keeps source identity immutable and prevents frequent
`last_opened_at` writes from rewriting the record that decides which directory this is.
Catalog scanning validates both files and reports a missing or mismatched pair as an
incomplete entry.

### Pinned checkout

`gitroot` is an ordinary checkout pinned to `active_revision`. Metabrowser never edits,
stages, pulls, merges, resets, or switches it in place.
The read-only guarantee is an ownership rule rather than blanket filesystem permissions,
which would interfere with cleanup on some platforms.

A Git refresh may add objects and atomically move remote-tracking refs, but it does not
change `gitroot` or `active_revision`. Selecting a newer revision constructs and
validates a replacement in staging, then promotes it only when no live session serves
the entry. A live session remains pinned to the root it opened.

If an integrity check finds a dirty cached worktree, Metabrowser reports it as
externally modified.
It does not reset or absorb the changes.
Rebuild and purge remain explicit.

## URL Resolution and Acquisition

Phase 1B accepts:

- `https://host/path/to/repository` and `https://host/path/to/repository.git`;
- `ssh://user@host/path/to/repository.git`; and
- SCP-like `user@host:path/to/repository.git`.

The CLI currently annotates `root` as `Path | None`, so Typer converts a URL before the
command body and collapses `https://` into path syntax.
The boundary changes to `str | None`. URL classification runs on the original value;
path-only modes construct and resolve `Path` only after remote-source resolution
declines it.

Inputs beginning with `-`, containing credentials, using unknown schemes, or resolving
to Git helpers such as `ext::` are rejected before Git sees them.
Production clone policy sets `protocol.allow=never` and explicitly enables only HTTPS
and SSH. Repository-root GitHub URLs are generic clone inputs.
Tree, blob, commit, issue, and pull-request URLs remain unsupported until a provider
phase can resolve them unambiguously.

Acquisition publishes one complete entry:

```text
classify source
  -> derive identity and lock it
  -> clone into same-filesystem staging
  -> resolve and pin HEAD
  -> validate gitroot and both records
  -> rename entry with no replacement
  -> serve immediately
  -> continue optional object backfill in background
```

All Git work continues through `metabrowser.git.process.run_git`. The runner gains
request, acquisition, and background policies rather than a parallel subprocess wrapper.
Every policy retains fixed arguments, no shell, bounded output, cancellation cleanup,
and scrubbed repository-pinning environment variables.
Acquisition also sets `stdin=DEVNULL`, disables terminal and credential-manager prompts,
uses SSH batch mode, and disables submodule recursion, hooks, automatic maintenance,
unsafe transports, and symlink materialization.

A cache hit validates the entry and serves its existing `gitroot` without fetch,
credential lookup, or background refresh.
This rule is observable and tested.
A failed backfill leaves the published entry usable and honestly marked partial; it does
not turn a successful open into a fatal error.

## Generic Cache Operations

Phase 2 builds a catalog by scanning validated repository entries.
Correctness does not depend on a central mutable database.
An optional derived index may later improve a measured startup cost, but it must be
disposable and reproducible from entry records.

The generic operation set is:

```shell
metab --repos
metab --repo-inspect <identity-or-slug>
metab --repo-refresh <identity-or-slug>
metab --repo-purge <identity-or-slug>
```

Refresh fetches Git refs, retries object backfill, and reports its stage results.
It has no provider stage in Phase 2. Provider plugins register refresh work only after
the provider framework lands; a plugin failure can then be reported without changing a
successful Git result.

Purge begins as a dry run, resolves exactly one identity, refuses live entries, and
moves the entry to recoverable trash before deletion.
List and inspect report identity, source, active revision, object state, size, last
open, last fetch, integrity, and any quarantine state.

## GitHub Browsing Content Model v1

“Full GitHub content model” is bounded here to the read-only repository-browsing domain.
GitHub exposes many administrative and product APIs that do not contribute to browsing
source, issues, or code review.
Claiming to model all of them would leave the phase with no completion criterion.

Phase 4 models the complete v1 browsing set before Phase 5 performs an API request.
It lands Pydantic models, compiled SoftSchema contracts, field documentation, normalized
fixtures, invalid fixtures, relationship tests, and a format inventory.
No renderer reads a provider record that the inventory does not register.

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

Phase 4 freezes the exact field set and enum policy from representative fixtures.
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
dependency. Phase 4 defines and fixtures the record.
Phase 7 implements derivation and navigation after ordinary PR snapshots and views are
stable.

## Provider Snapshot Storage

GitHub records are mutable observations, but cache publication should still be atomic
and old data should remain readable during refresh.
The provider directory begins in Phase 5:

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

The physical layout remains an implementation hypothesis until Phase 4 fixtures measure
path length, object counts, YAML size, parse time, and snapshot duplication.
The invariants are fixed: immutable snapshots, atomic current manifests, strict
contracts, safe path keys, explicit completeness, and no cross-entry writes.
If measurement favors a sharded or indexed equivalent, the architecture map and layout
format must say so before Phase 5 writes released data.

Raw API responses are not authoritative and are not stored by default.
A future bounded diagnostic capture, if justified, belongs under a separate
content-addressed namespace, removes secrets and volatile headers, and has an explicit
retention policy.

## GitHub Acquisition Boundary

Phase 5 adds a built-in GitHub plugin after the model phase.
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

## Security and Trust

A fetched repository and every provider string are third-party content.
URL-opened roots automatically use the untrusted profile and never expose edit
capabilities. Repository files cannot configure the application; a fetched
`.metabrowser/config.yml` is ordinary browsed content.

Clone inputs are untrusted.
The transport allowlist, option separator, no-prompt environment, timeout and output
bounds, no submodules, disabled hooks, patched-Git floor, and atomic publication are
security requirements, not convenience flags.

Provider records are validated before publication and bounded by file, field, and
collection limits established from fixtures and browser measurements.
Markdown and HTML from issues, pull requests, and comments use the existing untrusted
rendering policy. Schema selection comes from the installed registry, not from a
cache-supplied path.
Provider object IDs and URLs never become filesystem paths without safe encoding and
containment checks.

## Phased Implementation Plan

### Phase 0: Design evidence and contract freeze — current PR

- [ ] Remeasure full, blobless, and blobless-plus-backfill acquisition against the
  v0.8.0 history list, commit summary, comparison manifest, and deferred patches.
- [x] Review upstream through v0.8.0 and remove assumptions superseded by shipped Git
  history, revision, and diff infrastructure.
- [x] Review SoftSchema v0.7.0 and its enforced-composition boundary; install its Codex
  skill for future implementation turns.
- [x] Separate generic cache delivery, cache operations, chooser, GitHub modeling,
  GitHub acquisition, provider views, stack projections, and large-repository work.
- [ ] Freeze the safe URL grammar, source identity, slug, lock, staging, publication,
  quarantine, and trash state machines as fixtures.

### Phase 1A: Format foundation — infrastructure PR

- [ ] Add the application-home resolver, `config.yml`, `cache/layout.yml`, format
  history, future-format failure, and sequential migration harness.
- [ ] Adopt the released SoftSchema package after dependency and lock review; register
  the config, layout, repository identity, and repository state contracts.
- [ ] Package deterministic compiled schemas and add compile-drift, corpus-validation,
  schema-inventory, and installed-wheel checks.
- [ ] Add atomic YAML reads/writes, application-home locking, quarantine, and
  recoverable-trash primitives without cloning or serving a URL.
- [ ] Prove config preserves unknown settings while machine records reject unknown
  fields and cache-controlled schema paths cannot redirect validation.

### Phase 1B: Generic Git cache and URL open — first usable feature PR

- [ ] Change the CLI root boundary from `Path | None` to `str | None`; preserve URL
  bytes until classification and keep path-only modes receiving resolved paths.
- [ ] Add conservative source normalization, full identity digest, readable uniquified
  slug, collision verification, and per-source locking.
- [ ] Extend `git/process.py` with version detection, `stdin=DEVNULL`, non-interactive
  environment controls, and explicit acquisition/background policies.
- [ ] Clone to same-filesystem staging, resolve and pin HEAD, validate records and
  checkout, and publish with no replacement.
- [ ] Reuse a valid cache hit without network access, provider detection, or credential
  lookup.
- [ ] Start measured object backfill only after serving; persist honest partial,
  backfilling, complete, and failed states.
- [ ] Force the untrusted profile for URL-opened roots once `mb-vib1` lands.
- [ ] Add CLI goldens and docs for first open, cache hit, offline reuse, unsafe input,
  interrupted clone, and repair guidance.

### Phase 2: Generic catalog, refresh, and cache management

- [ ] Scan validated identity/state pairs into one provider-neutral catalog.
- [ ] Add list, inspect, Git-only refresh, repair diagnostics, and recoverable purge.
- [ ] Fetch and prune refs without changing `gitroot`; stage promotion separately and
  refuse to replace a live root.
- [ ] Add coordinated job progress, cancellation, stage outcomes, and process-safe races
  among open, refresh, promote, repair, and purge.
- [ ] Add size accounting and `CACHEDIR.TAG`; select no automatic eviction policy until
  measured usage justifies one.

### Phase 3: Repository chooser and session switching

- [ ] Add a chooser over the generic catalog with recent, favorite, offline, partial,
  dirty, and refresh states.
- [ ] Make root selection session-scoped rather than mutating global settings.
- [ ] Preserve each repository’s selected path, Git scope, and revision-navigation state
  as bounded client state.
- [ ] Measure warm-cache first paint and choose eager, prefetched, or on-demand asset
  tiers from observed cost.

### Phase 4: GitHub browsing model and schema corpus — no network

- [ ] Write the contract inventory in this plan as Pydantic models and deterministic
  compiled schemas, using simple closed objects and local `$defs`.
- [ ] Define stable IDs, repository refs, Git object refs, provider timestamps,
  retrieval metadata, completeness, pagination, tombstones, and unknown enum handling.
- [ ] Define issue, PR, review, thread, comment, check, status, timeline, and stack
  relationships without an opaque payload field or raw API authority.
- [ ] Build representative normalized fixtures for open, closed, merged, draft, forked,
  deleted, inaccessible, partial, paginated, outdated-anchor, unknown-enum, and stacked
  cases.
- [ ] Measure the proposed immutable-object and atomic-manifest layout; freeze or revise
  it before released provider data is written.
- [ ] Register every record and view surface in the architecture map and add an
  inventory test that fails when a contract lacks a producer, consumer, schema, or
  fixture.

### Phase 5: GitHub binding, acquisition, and provider cache

- [ ] Add the provider storage interface, namespace allocation, immutable snapshot
  writer, sync manifest, and atomic current pointers.
- [ ] Add GitHub repository binding without changing generic cache identity.
- [ ] Map bounded REST or GraphQL responses into the Phase 4 contracts; support
  conditional requests, cursors, rate limits, tombstones, and partial outcomes.
- [ ] Fetch repository, selected issue, and selected PR bundles on demand; keep the last
  completed manifest readable on refresh failure.
- [ ] Ask core to fetch selected provider refs, and record availability for every Git
  object reference.
- [ ] Add refresh controls and stage-level diagnostics without making provider refresh
  part of a generic cache hit.

### Phase 6: GitHub repository, issue, and pull-request views

- [ ] Add plugin-owned repository and issue views with explicit loading, stale, partial,
  unavailable, offline, and refresh states.
- [ ] Render PR comparisons through the existing Git adapter, File Diff Format, and diff
  plugin.
- [ ] Layer title, author, state, checks, reviews, threads, and freshness around the Git
  comparison; preserve incomplete-collection indicators.
- [ ] Render changed Markdown at the PR head through the existing revision-content path.
- [ ] Map review anchors only when their Git identity and line context are sufficient;
  otherwise show the original anchor as outdated or unresolved.

### Phase 7: Stacked pull requests and cross-object projections

- [ ] Implement stack derivation against the Phase 4 contract with explicit evidence,
  algorithm version, conflicts, and cycles.
- [ ] Add adapter points for explicit stack metadata without hard-coding a third-party
  tool into core or treating heuristics as fact.
- [ ] Add stack navigation, aggregate status, and adjacent comparisons as derived views
  over immutable PR and Git snapshots.
- [ ] Recompute projections when any input snapshot changes; never mutate source PR
  records to store derived order.

### Phase 8: Measured very-large-repository support

- [ ] Revisit shallow plus progressive deepening only for repositories whose measured
  acquisition cost justifies the added state model.
- [ ] Mark truncated history and disable blame while `.git/shallow` exists.
- [ ] Coordinate deepening with unbounded-history session design instead of adding a
  second pagination model.

## Phase Dependency Map

| Phase | Depends on | Does not depend on | User-visible result |
| --- | --- | --- | --- |
| 1A format foundation | Phase 0 contract decisions | GitHub, chooser | Versioned app home and strict cache records |
| 1B generic Git cache | 1A, untrusted-profile gate for serving | GitHub API or schemas | Any supported clone URL opens or reuses one local read-only entry |
| 2 cache operations | 1B | Provider support | Generic list, inspect, refresh, and purge |
| 3 chooser | 2 catalog | GitHub | Instant switching among cached repositories |
| 4 GitHub model | 1A format rules; may proceed alongside 2–3 | Network credentials, UI | Reviewed contract corpus for the full browsing domain |
| 5 GitHub acquisition | 2 job/storage primitives, 4 schemas | Provider UI | Refreshable, atomic offline GitHub snapshots |
| 6 GitHub views | 5 snapshots, shipped Git/diff paths | Stack derivation | Repository, issue, and PR reading |
| 7 stacked PRs | 4 stack contract, 5 snapshots, 6 navigation | New Git content model | Provenance-bearing stack navigation |
| 8 large repositories | Measurements from 1B and real use | GitHub | Explicit bounded behavior for exceptional repository scale |

Phase 4 may run in parallel with generic chooser work because it writes only schemas,
fixtures, and design registrations.
Phase 5 waits for both the model and the generic job and storage primitives.

## Testing Strategy

The ordinary suite uses local fixture repositories and an isolated `METABROWSER_HOME`;
it never requires the network or a real credential store.
Test acquisition explicitly allows the local protocol for fixture remotes.
Production policy cannot select that override.

- **Format and migration:** old released config migrates stepwise and idempotently; a
  future layout or contract fails before mutation; config extensions survive; registry
  binding outranks document metadata; compiled schemas cannot drift.
- **Identity:** documented equivalent URL syntax reuses one entry; preserved
  distinctions do not; forced short-digest collisions extend the slug; query, fragment,
  credentials, controls, and unsafe transports fail before Git.
- **Publication:** interruption at every staging boundary leaves no visible incomplete
  entry; `repository.yml`, `state.yml`, and HEAD agree before rename; a cache hit needs
  no network.
- **Read-only behavior:** browse and ref refresh leave `git status --porcelain` empty
  and `active_revision` unchanged; an externally dirtied entry is reported rather than
  reset.
- **Concurrency:** two opens share one completed entry; open, refresh, promotion,
  migration, repair, and purge cannot race across processes.
- **Git integration:** cached roots satisfy repository-root discovery, history, direct
  revisions, commit summaries, and bounded diff rendering before and after backfill.
- **Trust:** URL roots receive the untrusted capability set, never serve `.git`, and
  cannot promote repository-local metadata to host config.
- **Provider contracts:** every valid fixture passes structural and semantic validation;
  every invalid fixture fails with a stable code and path; unknown provider enum values
  normalize without opening the record schema.
- **Provider snapshots:** multi-page and partial refreshes publish only complete
  manifests; a failed refresh leaves the old current set; deletion, permission loss,
  not-requested, and rate-limit outcomes remain distinct.
- **Relationships:** all references resolve within a manifest or carry an explicit
  unavailable state; stack cycles and missing members are reported, not repaired by
  guessing.
- **Distribution:** the installed wheel contains every registered model, compiled
  schema, plugin asset, and format inventory.
  `make verify` remains the handoff gate.

## Rollout and Compatibility

Phase 1A and acquisition internals may land while the untrusted-profile dependency is
open. The URL-to-serve route remains disabled until a remote root is forced into that
profile. Local-path behavior does not change.

`f01` and every listed v1 contract are unreleased at the time of this plan.
There is no legacy cache reader to preserve yet.
Once released, a change must identify the consumer or persisted data that cannot update
with the producer, then choose migration, multi-contract reading, quarantine, or refresh
based on that concrete obligation.

Provider cache data is expendable only when it can actually be reacquired.
Offline and deleted sources retain their last validated immutable snapshots until an
explicit retention or purge operation removes them.
Generic Git data and user config receive the more conservative repair rules described
above.

## Decisions Deferred to Their Evidence Phase

- Phase 0 selects full versus blobless initial acquisition from current route
  measurements.
- Phase 4 selects the physical snapshot sharding after fixture counts and parse costs
  are measured. Its logical contracts and atomic-publication invariants are not open.
- Phase 5 selects REST, GraphQL, or a hybrid per acquisition need.
  Durable records do not expose that transport choice.
- Automatic eviction waits for Phase 2 size data and remains absent unless a defensible
  default follows.
- A live session either retains its pinned root until reopen or explicitly accepts a
  staged replacement; background refresh never switches it silently.

## Acceptance Criteria for the First Usable Phase

Phase 1B is complete when:

- `metab <supported-repository-url>` publishes one validated entry under
  `~/.metabrowser/cache/repos/<uniquified-slug>/gitroot` and serves it with the
  untrusted profile;
- repeating the command opens the cached root without clone, fetch, provider detection,
  credential lookup, or network access;
- `repository.yml` names one credential-free source identity, while `state.yml` names a
  full active revision and honest object state;
- browsing and Git ref refresh do not modify the working tree or active revision;
- interrupted and concurrent clones, an unsafe URL, future format, corrupt record,
  missing credential, unavailable network, and failed backfill each produce bounded and
  truthful outcomes;
- Files, Git history, direct revision, commit summary, and diff views work against the
  cached root under the same contracts as a local repository; and
- no GitHub API, provider credential, provider schema, or GitHub-specific branch is
  required to satisfy any criterion above.

## References

- [Repository cache and open from a Git URL](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
  — acquisition measurements, prior art, and the dated research record
- [Repository-library and GitHub-model design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
  — findings resolved by this rewrite
- [Git graph view](plan-2026-08-06-git-graph-view.md) — shipped Git history and the
  repository-root boundary
- [General diff rendering](plan-2026-08-17-general-diff-rendering.md) — comparison model
  and one acquisition workflow
- [Git revision navigation performance](plan-2026-08-25-git-revision-navigation-performance.md)
  — current revision loading and comparison behavior
- [Unbounded virtualized Git history](plan-2026-08-25-unbounded-virtualized-git-history.md)
  — future history continuation and virtualization
- [HTML rendering and trust model](plan-2026-08-06-html-rendering-and-trust-model.md) —
  untrusted-content dependency
- [tbd on-disk format versioning](https://github.com/jlevy/tbd/blob/v0.8.1/docs/tbd-format-versioning.md)
  — fail-closed layout formats and ordered migration publication
- [SoftSchema v0.7.0 guide](https://github.com/jlevy/softschema/blob/v0.7.0/docs/softschema-guide.md)
  — profiles, contract maturity, host registries, and artifact validation
- [SoftSchema v0.7.0 specification](https://github.com/jlevy/softschema/blob/v0.7.0/docs/softschema-spec.md)
  — portable YAML, enforced validation, schema binding, and compatibility rules

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
