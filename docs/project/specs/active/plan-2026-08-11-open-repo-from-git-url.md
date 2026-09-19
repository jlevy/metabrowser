# Feature: Repository Library and Open from a Git URL

**Date:** 2026-08-11 (rewritten 2026-08-26; refreshed 2026-09-16)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Shared-store design correction under review; v0.11.0 implementation is
release-gated

## Vision

Metabrowser should open a remote repository as easily as a local directory:

```shell
metab https://github.com/pallets/flask
```

The first open acquires the repository into a versioned application cache.
Later opens reuse immutable Git objects immediately, without consulting the network.
The cache becomes a local repository library: durable enough to make commonly opened
repositories feel local, but recoverable from its source when a store is damaged.
It owns no shared checkout or index; each view pins a full object ID and reads its tree
and blobs directly.

The initial product slice is deliberately provider-neutral.
A GitHub clone URL is an ordinary Git source in this phase.
Opening it must not require the GitHub API, a GitHub account, provider detection, or a
GitHub-specific record.
That boundary lets basic cache support land and prove itself before provider metadata
expands the system.

Later phases add generic cache operations and a repository chooser.
Hosted review starts with a separate provider-neutral content-model phase: strict,
versioned records for repositories, change requests, reviews, checks, comments, and
activity projections, with GitHub as the first adapter and GitLab a named future
consumer. The primary change-request artifact uses SoftSchema frontmatter: YAML holds
consumed values and the Markdown body holds the PR description.
Only after those contracts and a representative fixture corpus are accepted does the
`gh api` adapter write them or a plugin view consume them.

Git remains authoritative for repository content, history, and diffs.
Provider records describe hosted state and refer to immutable Git object IDs; they do
not replace the object database.

The
[repository-cache research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
contains the acquisition measurements and prior-art survey.
Its 2026-08-26 addendum separates dated evidence from the current design after Git diff
and revision navigation shipped; the 2026-09-14 refresh rebases the plan on the v0.10.0
inventory, identity, lifecycle, and parity contracts.
The 2026-09-16 correction replaces the pinned-checkout and detached-worktree proposal
with the shared repository-subject and provider-mirror architecture in
[Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md).
The
[design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
records the changes that produced this phased plan.

## Release Principle

Each phase below is an independently reviewable pull request or a short sequence of pull
requests with one acceptance boundary.
In particular:

- The format foundation can land without cloning a repository.
- The generic Git cache can land without catalog UI or GitHub code.
- Hosted-review schemas can land with fixtures and validation before any network
  acquisition.
- GitHub acquisition can land before plugin-owned hosted-review views.
- Derived stack navigation can land after ordinary pull-request reading is stable.

No phase reserves an opaque extension object for work that has not been modeled.
A later record family receives its own contract, storage path, producer, consumer, and
invalidating tests.

### v0.11.0 Milestone

The first v0.11.0 slice ends at offline-reusable views of any authorized GitHub
repository, any branch that repository exposes, and any directly addressed pull request,
not at the entire repository-library roadmap.
It includes Phase 0, Phase 1A, generic acquisition, repository URL opening, immutable
revision subjects, the narrow provider job and selected-ref foundation in `mb-jlon`, the
bounded `gh api` transport and auth work in `mb-p4sw`, the broker-pinned Git credential
bridge in `mb-s123`, and the common hosted-review and GitHub work in the
[provider plan](plan-2026-08-27-github-provider-and-pull-requests.md).

Full generic cache management, the in-app chooser, GitHub issues, stacked pull requests,
and very-large-repository acquisition remain in their existing later phases.
The GitLab adapter remains `mb-51uj` after the GitHub-first contracts and views ship.
This is a milestone boundary, not a scope deletion: `mb-0ybg`, `mb-vmzy`, `mb-9rrc`,
`mb-glxc`, and `mb-dqvj` retain that work.

`mb-xxhi` is the hard implementation gate.
It depends on the v0.10.0 release bead `mb-i57d` and closes only after the tag and
release are cut from the intended `main` commit, that commit is fetched locally, and the
first v0.11 implementation branch starts from it.
Every `release:v0.11.0` implementation bead depends on this gate; design and review work
may land before it.

## Goals

- Accept any common repository URL anywhere the CLI currently accepts a root path: clone
  URLs, and provider web URLs reduced to the repository they name.
- Open what the URL pointed at, not merely the repository containing it — a `/blob/` URL
  opens that file, a line anchor selects those lines.
- Resolve every branch the acquired remote exposes to a full object ID and serve its
  immutable tree without a checkout, index, branch switch, or detached worktree.
- Preserve the root argument as a string at the Click/Typer boundary, then classify it
  before any `Path` construction can rewrite URL syntax.
- Derive one stable source identity from the credential-free clone source, attach it to
  one shared repository-store identity, and reuse that store on every later open.
- Publish a worktree-free Git store only after its objects, refs, and metadata validate.
- Keep user-owned working trees outside cache authority.
  Fetching or provider refresh must never dirty them or silently advance their branches.
- Make a cache hit an offline operation for everything the entry actually contains.
  Network work begins only for a missing entry or an explicit refresh — and for a
  blobless entry, file content is subject to the lazy-fetch policy Phase 0 chooses
  rather than being silently exempt from this goal.
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

- Materializing a cached working tree.
  URL-opened revision subjects receive no file-mutation capabilities and need no working
  tree.
- Automatically advancing a live checkout when a remote ref moves.
  Fetch, select, and promote are distinct operations.
- Requiring provider support for the first usable cache.
  GitHub API access, credentials, and hosted-review schemas are not on the Phase 1B
  critical path; the provider plugin’s no-network URL reducer is part of opening common
  GitHub web URLs.
- Mirroring every GitHub API. The first provider model covers repository browsing and
  review. Organization administration, Projects, Actions logs, packages, billing,
  security alerts, and other account surfaces are outside its v1 scope.
- Using raw GitHub REST or GraphQL responses as the durable application model.
- Writing to GitHub. Provider support remains read-only through the phases in this plan.
- Storing provider credentials in `config.yml`, repository records, or provider
  snapshots.
- Treating a repository’s own `.metabrowser/` directory as trusted configuration.
  Everything read from a repository subject is untrusted repository content.
- Automatic LRU eviction before measurements establish a size and age policy.
  Explicit inspection and recoverable purge come first.
- Supporting arbitrary Git transports.
  Production permits HTTPS, SSH, and `file://`; helpers such as `ext::` and the
  unauthenticated `git://` protocol remain disabled, as does `git clone`’s implicit
  `--local` path form.
  See [Safety at the boundary](#safety-at-the-boundary).

## Current Foundation and Dependencies

The v0.10.0 release candidate establishes the implementation baseline for this plan:

- `metabrowser.git.process` is the only Git subprocess path.
  It already provides fixed arguments, bounded output, timeouts, concurrent stream
  draining, cancellation cleanup, repository-environment scrubbing, and typed failures.
- `/api/git/log`, direct revision routes, commit detail, and Git-backed comparisons use
  full object IDs; their Git command target must be generalized from `cwd` to a trusted
  worktree or worktree-free repository handle.
- The diff plugin renders File Diff Format rather than a provider response.
  A future PR view can therefore resolve provider refs to object IDs and reuse the same
  pipeline.
- The inventory engine now crosses one sealed provider-neutral contract, with coherent
  paged reads, joined shutdown, and explicit lifecycle state.
  The revision-content phase adds a sibling immutable content source rather than
  pretending Git-tree entries have filesystem mtimes, ignore state, or watcher events.
- API paths and browser URLs now use escaped inventory identities consistently.
  GitHub web-URL reduction must produce selections through that canonical codec rather
  than inventing a provider-specific path spelling.
- CLI parity now checks registered routes, kinds, models, persisted state, and declared
  user-visible functional aspects.
  Every cache and provider route, record projection, and interaction controller added
  here needs its architecture-map row and exact production-path golden in the same
  change.
- URL-opened roots remain gated on the untrusted capability profile tracked by
  `mb-vib1`. Cache storage and clone components may land before that gate; serving
  fetched content may not.
  That gate is larger than one bead and is sequenced explicitly below — see
  [The gate that decides when this ships](#the-gate-that-decides-when-this-ships).
- Metabrowser already depends on Pydantic, JSON Schema, ruamel.yaml, PyYAML, and
  frontmatter-format. SoftSchema remains a proposed first-party package over the same
  boundary, but Phase 1A selects an exact release from current metadata rather than
  carrying the plan’s former v0.7.0 pin forward.
  SoftSchema v0.8.1 was published on 2026-09-11 and fixes serialization of semantic
  `model_validator` failures, which cache validation must report as data rather than
  turn into a second exception.
  The project owner has confirmed that packages published from the `jlevy` first-party
  namespace are exempt from the 14-day delay.
  Phase 1A may therefore adopt v0.8.1 without waiting until 2026-09-25, but it must
  still review that exact release against v0.8.0, add the SoftSchema row to
  [`SUPPLY-CHAIN-SECURITY.md`](../../../../SUPPLY-CHAIN-SECURITY.md), verify released
  metadata and artifact hashes, update `uv.lock`, and run the full supply-chain and
  distribution gates.

The v0.10.0 revision and PR-facing comparison path needs blobs.
Blobless clone followed by background backfill remains the leading acquisition strategy,
but Phase 0 must remeasure the complete current route before promising a timing or
selecting a threshold between full and blobless acquisition.

## The Gates That Decide When This Ships

The first gate controls when v0.11 implementation starts: `mb-i57d` cuts v0.10.0 from
the intended `main`, then `mb-xxhi` verifies and fetches that commit before an
implementation branch is created from it.

The second gate controls when acquired content may be served.
A fetched repository is third-party content, so serving one requires the untrusted
capability profile. That profile is `mb-vib1`, which is blocked by `mb-cun0` — sandboxed
`/raw` responses and same-origin proof on `/api`. Both are open `P1` tasks belonging to
[the HTML rendering and content-trust plan](plan-2026-08-06-html-rendering-and-trust-model.md),
which is `Status: Draft` with nothing implemented.

```text
mb-i57d  release v0.10.0 from main
   └──► mb-xxhi  verify released main and open v0.11 implementation
           ├──► cache format, acquisition, source boundary, immutable projection (mb-z335)
           └──► mb-cun0  sandbox /raw, same-origin proof on /api
                    └──► mb-vib1  capability set and --untrusted profile
                              └──► mb-d658  reviewed trust-chain PR, stacked after mb-z335
                                       └──► mb-j439  integration base for repository URL open
                                                └──► mb-ew38  repository URL open
                                                         └──► mb-innz  reviewed URL-open PR
                                                                  └──► mb-jlon  selected-ref jobs
                                                                           └──► mb-bf94  reviewed job PR
                                                                                    └──► mb-2xq7  selected branch
```

Two consequences, both worth stating plainly rather than discovering during
implementation:

- **Every estimate for this feature must include that chain.** The cache work alone does
  not produce a user-visible result; the first thing anyone can actually open is gated
  on a security workstream in another document.
- **After the release gate, the trust and cache lanes are independent.** `mb-cun0` and
  `mb-vib1` have no dependency on the cache or Git status beyond their own order, so
  they can proceed in parallel with Phase 0 through 1B-c. Sequencing them alongside
  rather than after keeps the serving gate off the post-release critical path.
  Because the formal stack is linear, their reviewed PR (`mb-d658`) publishes directly
  after the immutable Git-tree source and becomes the base for repository URL opening.

This plan does not absorb that work or restate its design.
It records the dependency, names the beads, and treats “serving is gated” as a
scheduling fact with a shape rather than a footnote.

## Ownership and Layering

The application home has four distinct ownership classes:

| Surface | Owner | Mutability | Recovery rule |
| --- | --- | --- | --- |
| `config.yml` | User and application migration code | Durable and editable | Migrate losslessly; never discard unknown user settings |
| Cache layout, source identity, and repository-store identity | Core cache service | Rare writes | Validate, migrate if released data requires it, otherwise quarantine |
| Shared repository store | Core Git cache service | Objects and Metabrowser-owned refs may grow; revision subjects are immutable | Reacquire missing objects or rebuild outside a live lease |
| Source aliases and attachments | Core repository and provider services | Rare writes | Re-resolve from credential-free source or provider identity; never persist a local path in provider state |
| Provider snapshots and manifests | Provider plugin through core storage APIs | Refreshable and repository-scoped | Keep current, last-complete, one diagnostic predecessor, and explicit archival pins; reclaim only unreachable generations |

Core owns application-home resolution, atomic file publication, locks, safe cache paths,
repository acquisition, Git refresh, and provider namespace allocation.
Provider plugins own their schemas, API adapters, normalized records, routes, renderers,
and styles. Core does not import a GitHub schema or branch on a GitHub object kind.

### Owner-only storage

Repository and provider cache content may be private.
Every Metabrowser-created application-home directory is `0700` and every file is `0600`
on POSIX; Windows uses an equivalent current-user-only ACL. Remote acquisition fails
closed when the application home or a cache ancestor is a symlink, belongs to another
principal, is group/world accessible, or cannot be verified and repaired.
An explicit permissive `METABROWSER_HOME` receives an actionable refusal rather than a
warning followed by a private write.
This rule does not prevent read-only browsing of an ordinary local path outside the
application home or attaching it to a provider mirror without modifying it.

### Lock order

Locks have disjoint scopes and one fixed order:

1. the application-home lock is used only for layout migration and global enumeration or
   sweeps;
2. a source-alias lock protects alias creation and compare-and-swap repointing;
3. repository-store locks, acquired in ascending `RepositoryStoreId` order, protect ref
   publication, object import, maintenance, and reclamation; and
4. a provider/resource lock protects one binding, staged publication, current-pointer
   update, or provider reclamation operation.

No network or provider process runs while any lock is held.
A job stages outside the locks, then acquires source-alias → ordered repository stores →
provider/resource as required, revalidates its generations, expected object IDs, and
authorization context, and publishes atomically.
The application-home lock is never acquired while holding either narrower lock.
Tests freeze this order and the concurrent refresh/read/purge/reclaim cases.

## Application Home and Cache Layout `f01`

The first released logical layout is:

```text
~/.metabrowser/
├── config.yml
└── cache/
    ├── layout.yml
    ├── locks/
    ├── staging/
    ├── trash/
    ├── sources/
    │   └── <uniquified-slug>/
    │       ├── source.yml
    │       ├── state.yml
    │       └── store-alias.yml
    ├── repository-stores/
    │   └── <store-key>/
    │       ├── store.yml
    │       ├── state.yml
    │       └── repository.git/
    ├── provider-bindings/
    │   └── <source-key>.yml
    └── provider-repositories/
        └── <provider>/<instance-key>/<repository-key>/
```

The exact sharding and directory names remain a Phase 0 measurement decision, but the
ownership is fixed: source aliases, shared Git stores, and stable provider repositories
are siblings. Provider observations never live under a source entry, and the Git store
contains no checkout.
A source holds exactly one provider binding, so each source key names one binding file.
Later schemas may change a physical spelling before release; they may not collapse those
owners.

`METABROWSER_HOME` overrides the application home for tests and advanced operation.
It is the only application-home override; Metabrowser has no cache-root setting today,
and Phase 1A does not add a second one.
Paths in config expand a leading `~` against the operator’s home and resolve relative
paths against the application home.
Config parsing never performs shell expansion or evaluates environment syntax stored in
YAML.

### Why one `~/.metabrowser/` rather than XDG directories

`f01` names directory semantics, so this choice is expensive to revisit and belongs in
the record rather than in whoever implements it first.

The XDG-conformant split would be `$XDG_CONFIG_HOME/metabrowser` for `config.yml` and
`$XDG_CACHE_HOME/metabrowser` for the repository cache, with
`~/Library/Application Support` and `~/Library/Caches` as the macOS equivalents.
That split has one genuine advantage: a cache under a platform cache directory is
already excluded by backup and cleanup tools that understand the convention.

One application home wins anyway, for reasons specific to this cache:

- The cache is not disposable in the way a platform cache directory implies.
  An entry may be the only local copy of a source that is now offline or deleted, which
  is why purge and migration are explicit operations here and why quarantine retains
  damaged entries rather than discarding them.
  Filing it where the platform advertises “safe to delete at any time” would misdescribe
  it.
- Config and cache must agree about identity and format.
  `f01` versions the two together and migration publishes `config.yml` last; splitting
  them across two roots with independent lifetimes creates exactly the divided authority
  this layout avoids.
- One root is one thing to point `METABROWSER_HOME` at, and one thing for a user to
  inspect, back up, or remove.

`CACHEDIR.TAG` is what recovers the backup-exclusion benefit without the split, which is
why Phase 1A writes it when the cache root is created rather than leaving it to a later
phase.

### Layout format versus record contracts

The `f01` marker and SoftSchema contract versions solve different problems:

- `f01` names application-home directory semantics and migration order.
- A contract such as `com.github.jlevy.metabrowser.cache:RepositorySource/v1` names one
  YAML payload shape.
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

### Reclaiming `staging/`, `trash/`, and quarantine

Retaining data is the right default here, but retention without a reclamation rule is
how a cache silently becomes the largest directory in a home folder.
Each of the three gets its rule in Phase 1A, when the directories are created, rather
than waiting for later catalog work after someone notices the disk:

| Directory | Retained because | Reclaimed by |
| --- | --- | --- |
| `staging/` | An in-progress clone must be invisible until it is complete | Age-based sweep at startup under the application-home lock, skipping any staging path whose lock is currently held |
| `trash/` | Purge should be recoverable for a moment, not forever | Purge deletes it at the end of its own run; the startup sweep removes anything a crashed purge left |
| Quarantine | The entry may be the only local copy of an unavailable source | Never automatically. Explicit inspect and purge only |

`staging/` is the one that actually leaks: an interrupted clone leaves a tree behind,
and the publication guarantee is only that no *visible incomplete entry* results, which
is a weaker property than “nothing is left on disk”.
A user who cancels two clones of a large repository has paid for both.

Quarantine is deliberately exempt from automatic reclamation, because the whole reason
an entry is quarantined is that Metabrowser could not establish what it is.
Deleting it on a timer would discard exactly the cases that most need a human to look.
What quarantine does owe the user is visibility, and Phase 1B is the first release that
can produce one: whichever open or migration path quarantines an entry says so and names
the retained path, so the directory is never a silent accumulation waiting for a later
`--repo-inspect` command to reveal it.

SoftSchema is the record boundary.
Hosted Review Phase 0C.1 selected, reviewed, and shipped the exact first-party release;
Phase 1A reuses that locked dependency rather than choosing another version.
The owner-confirmed `jlevy` exception removed the 14-day wait, not the exact-release
review. Runtime adoption continues to use the released package and committed lock, not a
Git checkout.

### Artifact profile and binding

Generic layout, identity, state, and cache-operation records use SoftSchema’s
`pure-yaml` profile.
Provider-owned document artifacts may choose another profile under their own format; the
hosted-review plan uses `frontmatter-md` for a change request whose Markdown body is the
PR description. Each file carries `contract`, `envelope`, and `status`. It omits
`softschema.schema` deliberately.
The application registry binds the contract ID to the schema packaged in the installed
Metabrowser wheel; an untrusted cache file cannot redirect validation to another path.

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
Core source/store identity and user config need a migration or a precise repair path
because they may be the only durable link to an unavailable source.

## Generic Repository Identity and Records

### Source identity

The cache key is a SHA-256 digest of a credential-free source identity.
The directory combines a readable slug with a short digest:

```text
github-com--pallets--flask--7d5c1a2e4b90
```

The full digest in `source.yml` is authoritative.
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
canonicalization. A later GitHub binding may prove that several conservative source IDs
name one stable repository and attach them to one `RepositoryStoreId` without changing
the source identities.
Existing stores are never merged from owner/name text or by discarding independently
acquired objects; stable opaque provider identity and complete object-format validation
are required before an alias can change.

### Stable identity and mutable state are separate

`source.yml` is written during source publication and does not change during ordinary
open or refresh:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:RepositorySource/v1
  envelope: source
  status: enforced
source:
  id: sha256:<full-source-identity-digest>
  slug: github-com--pallets--flask--7d5c1a2e4b90
  display_url: https://github.com/pallets/flask
  clone_url: https://github.com/pallets/flask
  transport: https
  created_at: "<RFC-3339 timestamp>"
```

`store-alias.yml` is a separately mutable, generation-checked attachment from that
source to one internal repository store.
A later verified provider binding may repoint the alias without rewriting `source.yml`;
publication retains the old store until no other alias, provider revision, or lease
reaches it.

`store.yml` is immutable identity and acquisition metadata for the worktree-free Git
database:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:RepositoryStore/v1
  envelope: store
  status: enforced
store:
  id: sha256:<internal-store-identity-digest>
  created_at: "<RFC-3339 timestamp>"
  acquisition:
    strategy: blobless
    git_version: "<version>"
    object_format: sha1
```

The store’s `state.yml` contains mutable Git state and is atomically replaced:

```yaml
softschema:
  contract: com.github.jlevy.metabrowser.cache:RepositoryStoreState/v1
  envelope: state
  status: enforced
state:
  default_remote_ref: refs/remotes/origin/main
  default_revision: <full-object-id>
  object_state: backfilling
  last_fetch_at: null
  last_operation:
    kind: acquire
    outcome: succeeded
    at: "<RFC-3339 timestamp>"
```

Separating source, alias, store identity, and store state prevents a moving ref, an
open, or later provider resolution from rewriting the record that decides what a source
is. Catalog scanning validates every referenced record and reports a missing or
mismatched pair as an incomplete attachment or store.

Source recency is optional bookkeeping in the source’s `state.yml`. An otherwise
offline, read-only cache hit may try to update `last_opened_at`, but that write must not
be able to fail the open.
A read-only home, full disk, or contended lock logs the dropped timestamp and proceeds
against the validated store.
Nothing in serving depends on recency; it is a Phase 3 chooser affordance, not a
correctness input.

This is a listed Phase 1B acceptance case, beside interrupted clone and unavailable
network: a cache hit against an application home the process cannot write must still
serve.

### Worktree-free repository store

The repository store is a Git object database with Metabrowser-owned refs and no shared
working tree or index.
Metabrowser never needs `checkout`, `switch`, `reset`, or `worktree add` to serve
repository content. A session selects a full object ID and reads its tree and blobs
directly through an immutable content-source handle.

A Git refresh may add objects and atomically move private remote-observation refs, but
it does not change an existing session descriptor.
A live session remains pinned to the object ID it opened while another client refreshes
or opens another branch.

User-owned working trees remain ordinary filesystem subjects.
The separate [Git-status plan](plan-2026-08-26-git-status-and-working-tree-diffs.md)
owns their local change semantics.
Provider activation and selected-ref fetching use the shared store and never reset,
absorb, or borrow objects through persistent alternates from a user’s checkout.

## URL Resolution and Acquisition

### The URL a person actually has

The product goal is that any repository URL works: paste what is in the address bar,
Metabrowser figures out which repository to check out, **and it opens what the URL was
pointing at**. Landing at the repository root when the URL named a file is a worse
outcome than it sounds — the reason someone pastes a `/blob/` URL is the file, not the
repository.

What people paste is almost never a clone URL:

```text
https://github.com/pallets/flask/tree/main/src/flask
https://github.com/pallets/flask/blob/main/src/flask/app.py#L120-L134
https://github.com/pallets/flask/blob/main/README.md?plain=1
https://github.com/pallets/flask/commit/1a2b3c4
https://github.com/pallets/flask/pull/5123
```

Every one names the same repository, unambiguously, in its first two path segments.
Rejecting them because they are not clone URLs would fail on the most common input while
the answer sits in plain sight.

### The variants that must work

Phase 1B accepts clone URLs as given — `https://host/path/to/repository`, the same with
`.git`, `ssh://user@host/path/to/repository.git`, and the SCP-like
`user@host:path/to/repository.git`.

It also reduces provider web URLs to a clone URL plus a selection.
The table covers the common shapes; “common” is the bar, and an unrecognized shape falls
back to opening the repository rather than failing:

| Web URL shape | Selection after clone |
| --- | --- |
| `/<owner>/<repo>` | repository root |
| `/<owner>/<repo>/tree/<ref>` | root at `<ref>` |
| `/<owner>/<repo>/tree/<ref>/<path>` | directory `<path>` at `<ref>` |
| `/<owner>/<repo>/blob/<ref>/<path>` | file `<path>` at `<ref>` |
| `/<owner>/<repo>/raw/<ref>/<path>` | file `<path>` at `<ref>` |
| `/<owner>/<repo>/blame/<ref>/<path>` | file `<path>` at `<ref>` |
| `/<owner>/<repo>/commit/<oid>` | `/commit/<oid>` |
| `/<owner>/<repo>/releases/tag/<tag>` | root at `<tag>` |
| `raw.githubusercontent.com/<owner>/<repo>/<ref>/<path>` | file `<path>` at `<ref>` |
| `/<owner>/<repo>/pull/<n>`, `/issues/<n>` | root, with the object named as unavailable |

Fragments and query strings are read for meaning and otherwise discarded:

| Carried | Dropped |
| --- | --- |
| `#L120`, `#L120-L134`, `#L120C5-L134C20` — line and column anchors become a selection within the file | `?utm_*`, `?ref=`, `?s=`, `?email_*` and other tracking parameters |
| `?plain=1` — asks for source rather than the rendered view | `?w=1`, `?diff=split` and other display parameters with no local equivalent |
|  | trailing slashes, duplicate slashes, and empty fragments |

Dropping a parameter is not silent when it changes what the user would see: a URL asking
for a display mode Metabrowser does not have opens the file and says which part of the
request it could not honor.

### What a selection addresses

`/view/<path>` addresses the content source selected by the session;
`/commit/<rev>[/<inner>]` addresses a change set.
The current source is a filesystem root.
The v0.11 slice adds an immutable Git-tree source rather than changing `/view` into a
checkout operation.

After acquisition, selection resolution turns the requested ref into a full object ID
and creates a leased `{repository_store_id, full_object_id}` subject.
Repository context names both the requested ref and resolved object ID so a copied URL
never implies that a moving branch name is immutable.
Directory listing uses `git ls-tree` semantics, bounded file reads use batched
`git cat-file`, and history and diff operations receive the same trusted worktree-free
Git command target.

The subject is a descriptor and lease, not a materialized tree.
It never creates or advances a local branch, never owns an index, and can coexist with
any number of other subjects over the same store.
Missing objects may trigger one bounded fetch of the explicit selected ref.
A cache hit with the object already present stays offline.
Archive extraction remains owned by the archive plugin, and review anchors remain
provider-domain data rather than filesystem bytes.
Only proven low-level lease and safe-path helpers may be shared across those owners.

This makes “any branch” precise: any branch advertised by the selected remote and
readable with the user’s Git credentials can be opened, including names with slashes.
A deleted branch, an object outside the configured fetch bounds, or a branch the user
cannot read yields a typed unavailable result rather than falling back to a different
revision.

Line and column anchors are carried through the parse, applied where the target view
supports a line selection, and reported rather than silently dropped where it does not.

### The ref and path boundary is ambiguous, and the clone resolves it

`/<owner>/<repo>/tree/<ref>/<path>` has no delimiter between the ref and the path, and
branch names contain slashes.
This URL is genuinely ambiguous:

```text
https://github.com/o/r/tree/feature/login/src/auth.py
```

The ref could be `feature`, `feature/login`, or `feature/login/src`. GitHub resolves it
server-side against its own ref list, which is why the ambiguity is invisible on the
web.

Metabrowser does not need an API to resolve it, because **after the clone it has the ref
list**. Reduction therefore produces a *candidate split set* rather than one answer, and
the selection step resolves it against the acquired repository: try the longest prefix
that names a real ref, then treat the remainder as the path.
A commit-shaped `<ref>` is checked as an object id first.
If no prefix resolves, the repository opens at its root and reports the unresolved
selection.

This is a case where doing the work locally is strictly better than the provider API
would be, and it is the reason selection resolution belongs after acquisition rather
than inside URL parsing.

**What it resolves against matters.** A fresh clone has exactly one local branch under
`refs/heads/`; every other branch exists only as `refs/remotes/origin/<name>`. Resolving
a bare branch name against local heads alone would find the default branch and nothing
else — the common case working by accident while every other case fails.
The candidate split resolves against remote-tracking refs and tags as well as local
heads, and an object-id-shaped `<ref>` is checked as an object first.

One URL shape spells that namespace out and must not be mistaken for the first two
segments of a path:

```text
https://raw.githubusercontent.com/<owner>/<repo>/refs/heads/<branch>/<path>
```

### Pull requests: the shape now, the content later

A `/pull/<n>` URL reduces to the right repository today, and the number is retained in
the resolved selection rather than discarded.
This phase reports that the pull request itself needs provider support and opens the
repository.

When the provider work lands, the same reduction feeds a pull-request view with no
change to URL handling — the parse already produced `(repository, pull_request, n)`.
Designing the reduction to carry an object it cannot yet render is what keeps that a
view change rather than a second URL implementation.

### Where provider knowledge is allowed to live

Reducing a web URL to a clone URL is provider-specific knowledge, and the layering rule
says the generic cache must not acquire any.
Both hold, because they are about different things.

The rule protects *identity and records*: the cache must not learn a provider’s notion
of equivalence, must not branch on a provider object kind, and must not import a
provider schema. Reducing `/blob/main/foo.py` to a repository is none of those.
It happens strictly **upstream** of the cache, needs no API, no credential, and no
provider record, and its entire output is an ordinary clone URL plus an inert selection
record that the cache never reads.

The mechanism is a small declarative table of host patterns and path shapes behind one
narrow interface, with GitHub as the first entry and GitHub Enterprise hosts
configurable against the same shapes.
Each installed reducer declares its schemes and hosts and returns `NotApplicable`,
`Reduced`, or `Rejected`. Exactly one reducer may claim an input; overlapping claims
fail plugin discovery, and a claimed-but-invalid URL returns terminal `Rejected` rather
than falling through to a different reducer or local-path parser.
The cache still computes identity from the resulting clone URL, so
[conservative normalization](#stable-identity-and-mutable-state-are-separate) is
untouched: two spellings that reduce to the same clone URL share an entry because the
clone URL is identical, not because anything guessed they were equivalent.

Reserved namespaces (`/settings`, `/orgs/…`, `/features`, `/sponsors`, `/marketplace`,
and the rest) are not repositories and must not be reduced to one.
The table lists what it recognizes rather than assuming every two-segment path is
`owner/repo`, and an unrecognized `github.com` path is refused with a message rather
than cloned hopefully.

### Safety at the boundary

The CLI currently annotates `root` as `Path | None`, so Typer converts a URL before the
command body and collapses `https://` into path syntax.
The boundary changes to `str | None`. URL classification runs on the original value;
path-only modes construct and resolve `Path` only after remote-source resolution
declines it.

Inputs beginning with `-`, containing credentials, using unknown schemes, or resolving
to Git helpers such as `ext::` are rejected before Git sees them.
Production clone policy sets `protocol.allow=never` and explicitly enables HTTPS, SSH,
and `file`.

**Local origins, decided 2026-08-28, revised 2026-08-30.** `cache/urls.py` classifies
transport as `https`, `ssh`, or `file`, and accepts `file://` URLs as Git sources.
`acquire` binds a `file` source to the untrusted profile unconditionally, which is where
a source nobody authenticated belongs anyway.

**A bare local path is not a Git source.** `metab /path/to/repo` keeps its existing
meaning — serve that directory — so the grammar has no ambiguity to resolve, and the
only way to ask for acquisition is the explicit `file://` form.

The first draft of this decision accepted bare paths too, and justified them as
“strictly safer” than the allowed transports.
That was wrong, and the reason is specific enough to record.
`git clone` given a path defaults to `--local`, which is not the git-aware transport at
all:

- it **hardlinks** `.git/objects` into the clone, so the entry is not isolated from
  later mutation of the source — verified on Git 2.50.1, where a loose object shows a
  link count of 2 from both sides; and
- it **ignores `--filter`**, warning
  `--filter is ignored in local clones; use file:// instead`, which silently defeats the
  blobless acquisition
  [this plan specifies](#blobless-acquisition-and-the-offline-guarantee).

So a path-form clone is neither safer nor the same code path.
`file://` goes through the git-aware transport and produces a pack rather than
hardlinks, which is what the isolation argument needs.
Pinning it is what makes the rest of this section true.

The decision is load-bearing for testing, which is the honest reason it came up.
Acquisition goldens clone from a `file://` origin built in the same sandbox, so they run
the real `run_git` on the real code path with no network and no mocking.
The alternative considered and rejected was a test-only escape hatch admitting local
origins, which would fork production and test logic — the thing
`tbd guidelines golden-testing-guidelines` warns against most directly, and which would
mean the acquisition path proved by CI was not the acquisition path users run.

Acquisition publishes one complete store and source alias:

```text
classify source
  -> derive identity and lock it
  -> acquire a worktree-free Git database in same-filesystem staging
  -> resolve and pin HEAD
  -> validate objects, refs, and records
  -> publish the store with no replacement
  -> create the source alias as the final visibility commit
  -> serve an immutable revision subject immediately
  -> continue optional object backfill in background
```

All Git work continues through `metabrowser.git.process`, which now exposes two seams:
`run_git` for bounded buffered commands, and `spawn_git_process` plus
`terminate_git_process` for a caller-owned streaming process.
Acquisition is a buffered command, so it uses `run_git`, which gains request,
acquisition, and background policies rather than a parallel subprocess wrapper.

Background backfill is the one piece that may want the streaming seam, and if it takes
it, the lifecycle rules that continuous history established apply in full: bound the
count, bound the storage, expire on idle, release on shutdown, and drain output before
reaping. See
[Git and comparison sources](../../architecture/arch-git-and-comparison-sources.md#long-lived-walks).
Every policy retains fixed arguments, no shell, bounded output, cancellation cleanup,
and scrubbed repository-pinning environment variables.
Acquisition also sets `stdin=DEVNULL`, disables terminal and credential-manager prompts,
uses SSH batch mode, creates stores with an empty Git template, and disables submodule
recursion, hooks, automatic maintenance, unsafe transports, and unsafe symbolic-link
traversal.

A cache hit validates the source and store and serves a full-OID subject without fetch,
credential lookup, or background refresh.
This rule is observable and tested.
A failed backfill leaves the published store usable and honestly marked partial; it does
not turn a successful open into a fatal error.

### Blobless acquisition and the offline guarantee

These two commitments are in tension, and the plan previously held both without
reconciling them:

- a cache hit is an offline operation, served without fetch; and
- initial acquisition is blobless, with backfill running afterwards.

A blobless clone does not contain file content.
Git fills that in lazily from the promisor remote at the moment something reads a
missing blob — so between publication and backfill completion, a read on a *server
request path* can attempt network I/O. The project’s own research observed exactly this
failure rather than reasoning about it: a blame in a blobless clone failed outright with
`could not fetch … from promisor remote` while the network was intercepted.

That makes “offline cache hit” true for history and tree structure and false for file
content, which is not a distinction a user should discover by having a request hang.

Phase 0 decides the policy and records it beside the
[version gates](#git-version-gates).
The options, in preference order:

1. **Disable lazy fetch on read paths** (`--no-lazy-fetch` / `GIT_NO_LAZY_FETCH`) and
   map a missing object to the existing `deferred` or `unavailable` availability, which
   backfill completion flips to `ready`. Reads stay bounded and offline by construction,
   and the honest partial state the plan already models carries the meaning.
   This needs its own floor row, since the option is recent — Phase 0 verifies the
   version.
2. **Gate blobless acquisition on that floor** and fall back to full clone below it, so
   there is never a published store whose reads can reach the network unexpectedly.
3. **Accept lazy fetch, bound it, and rewrite the guarantee** to what is true: history
   and tree structure offline, file content per `object_state`.

Option 3 is listed because it may be the right trade, not because it is the fallback: it
is the only one that keeps a blobless entry fully readable when the network *is*
available. What is not acceptable is keeping the current wording, which promises offline
reads that a blobless entry cannot deliver.

Whichever is chosen, “read of a not-yet-backfilled blob, online and offline” joins the
Phase 1B acceptance list beside interrupted clone and unavailable network.
It is currently the only adverse path there with no stated outcome.

### Git version gates

Phase 1B detects the Git version once and gates three separate things on it.
They are listed separately because they have different floors and different
consequences, and a single unnumbered “supported Git” would hide that:

| Gate | Floor | Below the floor |
| --- | --- | --- |
| Acquisition | **2.26** | URL opening is refused with a typed `unsupported_git_version` state naming the detected and required versions. Local-path browsing is unaffected |
| Blobless acquisition (`--filter=blob:none`) | **2.26** | Falls back to full clone |
| `git backfill` | **2.49** | Falls back to full clone at acquisition time; a published blobless entry is never left waiting for a command that does not exist |
| Cache integrity (`is_clean`) | **2.36** | Reported unavailable, never inferred clean — see the [Git-status plan](plan-2026-08-26-git-status-and-working-tree-diffs.md) |

The 2.26 floor makes protocol v2 the default and is the version the
[acquisition research](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
proposes; Phase 0 confirms it against the platforms this project supports.
`git backfill` gates separately at 2.49, is stamped experimental upstream, and is
treated as a pure optimization: the blobless-plus-backfill strategy is chosen only when
both the clone filter and the backfill command are available, so the fallback decision
happens before publication rather than stranding an entry in `backfilling` forever.
The same fallback applies when a remote refuses a partial clone.

Version detection degrades rather than refuses: an unparseable `git version` string is
treated as below every floor, which selects the conservative full-clone path, and the
detected string is recorded in `store.yml` under `acquisition.git_version` so a later
entry can be explained.

Separately from these capability floors, acquisition requires a Git release carrying the
fixes for the known clone-time vulnerabilities in submodule handling and symlinked
`.git` directories.
That floor tracks upstream advisories rather than a feature, so Phase
0 pins the exact version alongside the transport allowlist and records it beside this
table; it is not satisfied by 2.26 alone.

## Generic Cache Operations

Later catalog work scans validated source aliases and repository stores.
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
The initial generic operation has no provider stage.
Provider plugins register refresh work only after the provider framework lands; a plugin
failure can then be reported without changing a successful Git result.

Purge begins as a dry run, resolves exactly one alias or store identity, refuses live
leases, and moves only state no other alias or provider revision reaches to recoverable
trash before deletion.
List and inspect report source and store identities, selected revision, object state,
size, last open, last fetch, integrity, attachments, and any quarantine state.

## Hosted Review and Provider Support Live in Their Own Plan

Provider-neutral hosted-review modeling, GitHub acquisition, snapshot storage, plugin
views, virtual PR navigation, and stacked-change projections moved to
[the hosted-review and GitHub provider plan](plan-2026-08-27-github-provider-and-pull-requests.md).
That document and the
[hosted-review architecture](../../architecture/arch-hosted-review-model.md) own the
record families, storage layout, provider port, activity projection, and view boundary.

What stays here is the part the generic cache owes a provider, and it is deliberately
small: a stable source attachment, an optional shared repository store, atomic
publication, application-home locking, job progress and cancellation, and core-side Git
ref fetching on request.
Core provides repository-store and provider-resource ports and does nothing else
provider-specific — it does not import a provider schema, branch on a provider object
kind, or let provider state redefine generic source identity.

The one thing that is not deferred is the boundary itself, which is recorded in
[Git and comparison sources](../../architecture/arch-git-and-comparison-sources.md): Git
stays authoritative for content, history, and diffs, and provider records refer to
immutable Git object ids rather than replacing them.

## Security and Trust

A fetched repository and every provider string are third-party content.
URL-opened roots automatically use the untrusted profile and never expose edit
capabilities. Repository files cannot configure the application; a fetched
`.metabrowser/config.yml` is ordinary browsed content.

Clone inputs are untrusted.
The transport allowlist, option separator, no-prompt environment, timeout and output
bounds, no submodules, disabled hooks, the patched-Git floor in
[Git version gates](#git-version-gates), and atomic publication are security
requirements, not convenience flags.
Each has a stated version or value there; “recent enough Git” is not a security control.

Provider records are validated before publication and bounded by file, field, and
collection limits established from fixtures and browser measurements.
Markdown and HTML from issues, pull requests, and comments use the existing untrusted
rendering policy. Schema selection comes from the installed registry, not from a
cache-supplied path.
Provider object IDs and URLs never become filesystem paths without safe encoding and
containment checks.

## Implementation Coordinates

The v0.10.0 code has one filesystem root, one Git process boundary, and one inventory
lifecycle. The cache work generalizes those seams to a typed content source and trusted
Git command target; it does not add parallel ways to run Git or clear session-owned
state.

### Existing files to change

| File | Existing seam | Planned change |
| --- | --- | --- |
| `src/metabrowser/cli/main.py` | `_metab`, `_require_root` | Keep the root argument as a string-or-null value until root classification; do not construct a `Path` first |
| `src/metabrowser/cli/serve.py` | `run_serve` | Resolve or acquire before importing the configured server, install the selected repository subject, force the untrusted profile, and release its lease on shutdown |
| `src/metabrowser/cli/show_cli.py` | `run_show` | Use the same resolver so `--show` and `--api` inspect the exact repository or branch production serving would open |
| `src/metabrowser/git/process.py` | `run_git`, `spawn_git_process`, `terminate_git_process` | Add `GitCommandTarget` plus named read, acquisition, fetch, and batch-object policies with `stdin=DEVNULL`, non-interactive environment controls, distinct time/output bounds, and typed cancellation; no second Git runner |
| `src/metabrowser/paths_safe.py` | `_set_root_dir`, `register_root_callback` | Retain filesystem containment for attached roots; revision subjects resolve paths through the content source and never masquerade as local paths |
| `src/metabrowser/inventory_engine/coordinator.py`, `contract.py` | `InventoryCoordinator.replace_root`, `InventoryBackend.open`, `InventoryEntry`, `close` | Generalize lifecycle to `SourceSession`; preserve the filesystem inventory and define a distinct immutable-tree navigation index rather than fabricating mtimes |
| `src/metabrowser/repository_context.py` | `RepositoryContext`, `discover_repository_context` | Add `RepositorySubject`, attached-filesystem and Git-revision variants, and credential-free remote candidates; separate local path, source, store, and provider identities |
| `src/metabrowser/server.py`, `view_routes.py`, `sse.py`, `tree.py` | lifecycle, file/raw/tree/rollup/container/KPress/event routes | Resolve the active source session and capability envelope instead of assuming one global `Path`; close jobs, readers, and leases after history/inventory work joins |
| `src/metabrowser/plugin_api.py`, `plugin_loader/classify.py`, built-in sidekicks | path helpers, classification, data hooks | Add opaque bounded content-reader calls, retain filesystem-only path helpers, and capability-gate hooks that cannot operate on immutable content |
| `src/metabrowser/git/repo.py`, `routes.py`, `history.py`, `detail.py`, `log.py`; `src/metabrowser/diff/adapters/git.py` | repository discovery, history, refs, detail, and diffs | Accept a validated command target and explicit immutable subject OID; never infer a store subject from ambient `HEAD` |

### New core files and callable boundaries

| File | Key types and functions | Responsibility |
| --- | --- | --- |
| `src/metabrowser/home.py` | `application_home`, `ensure_home`, `validate_private_home` | Resolve `METABROWSER_HOME`, create owner-only layout paths, reject symlinked/foreign/permissive ancestors for remote content, and write `CACHEDIR.TAG` |
| `src/metabrowser/cache/records.py` | `ApplicationConfig`, `CacheLayout`, `RepositorySource`, `RepositorySourceState`, `RepositoryStoreAlias`, `RepositoryStore`, `RepositoryStoreState` | Strict Pydantic models and SoftSchema envelope bindings |
| `src/metabrowser/cache/layout.py` | `read_layout`, `migrate_layout`, `LAYOUT_FORMAT` | Fail closed on future formats and run ordered migrations |
| `src/metabrowser/cache/atomic.py` | `read_record`, `write_record_atomic`, `application_home_lock`, `source_alias_lock`, `repository_store_lock`, `provider_resource_lock` | Bounded reads, owner-only files, same-filesystem publication, fixed home → alias → ordered stores → resource order, and process-safe locking |
| `src/metabrowser/cache/identity.py` | `normalize_git_source`, `source_identity`, `repository_store_id`, `provider_repository_store_id`, `cache_slug` | Credential-free source identity, stable internal store identity, deterministic provider-identity store derivation, aliasing, and collision verification |
| `src/metabrowser/cache/urls.py` | `classify_root_argument`, `ProviderUrlReducer`, `ReducerOutcome`, `RepositorySelection` | Distinguish local paths, Git sources, and registered provider web URLs before constructing a `Path`; arbitrate declared reducer claims and terminal rejection; keep provider-specific syntax behind reducers |
| `src/metabrowser/cache/acquire.py` | `acquire_repository`, `validate_staging_store`, `publish_store`, `publish_source_alias` | Acquire and publish a validated worktree-free store, then create the source alias as the final atomic visibility commit |
| `src/metabrowser/cache/selection.py` | `resolve_selection`, `resolve_ref_path_candidates` | Resolve slash-containing branch/tag/path candidates against local and remote-tracking refs and return either a full object ID or a typed request for one explicit missing ref; performs no network work |
| `src/metabrowser/content_source.py` | `SourceSession`, `SourceCapabilities`, `ContentSource`, `ContentHandle`, `ContentEntry`, `list_directory`, `read_window`, `close` | Define one generation-owned source session for attached filesystems and immutable revisions without fabricating filesystem facts |
| `src/metabrowser/git/tree_source.py` | `GitPath`, `GitTreeSource`, `resolve_tree`, `list_tree`, `read_blob`, batch-reader actor lifecycle | Enumerate NUL-framed byte-safe full-OID trees and read size-gated blobs directly from the shared store |
| `src/metabrowser/provider_resources/models.py` | `AuthorizationContextRef`, `authorization_context_key`, `LocalObjectAvailability`, `LocalGitObjectAvailability` | Move the non-secret context record, its one canonical key function, and the local object-availability vocabulary and report out of the hosted-review plugin before core consumes them; the observation-guarded constructors stay in `hosted_review/models.py`, and `mb-s0gv` later moves the remaining neutral provider records |
| `src/metabrowser/plugin_api.py` | opaque `GitFetchCredentialLease`; `RepositoryObjectJobPort.request_selected_refs`, `provider_fetch_authorization_context` | Define the public opaque registry handle; validate an `AuthorizationContextRef`, derive its canonical key, and map the record once to an internal `ProviderPrincipal`; and let trusted provider plugins pass the handle without importing Git internals |
| `src/metabrowser/git/process.py` | `GitCommandTarget`, `run_git`, `spawn_git_process`, askpass bridge | Keep one Git subprocess boundary; in Phase 3A, project a validated broker credential under the environment, configuration, and prompt-binding isolation of the repository-source architecture without exposing its secret |
| `src/metabrowser/cache/repository_store.py` | `FetchAuthorizationContext`, `resolve_store`, `stage_fetch`, `publish_refs`, `lease_revision`, `converge_store`, `reclaim_objects` | Derive deterministic provider store IDs, isolate fetches by source and closed non-secret auth context, import staged objects, compare-and-swap refs and aliases, and protect leased and durable revisions |
| `src/metabrowser/cache/service.py` | `RepositoryOpenTarget`, `resolve_open_target`, `close_open_target` | Orchestrate parse, acquire/reuse, selection, immutable subject creation, trust profile, and initial browser path for CLI and later chooser callers |
| `src/metabrowser/cache/jobs.py` | `RepositoryJob`, `RepositoryJobRegistry`, `fetch_selected_ref`, `request_ref_fetch`, `GitFetchCredentialLeaseRegistry`, `validate_git_fetch_credential_lease`, `close_all` | Own bounded network fetch/prune for explicit selected refs plus provider-neutral progress, cancellation, the lease registry, per-request context/lease/source validation before job lookup, and stage outcomes used later by provider plugins |
| `src/metabrowser/cache/routes.py` | `api_cache_layout`, `api_cache_sources`, `api_cache_source`, `api_cache_stores`, `api_repository_jobs` | Read-only logical-state projections for CLI parity; acquisition remains a CLI action, not a write API |
| `src/metabrowser/cache/reclaim.py` | `reclaim_staging`, `reclaim_trash`, `reclaim_repository_objects` | Briefly enumerate under the home lock, then recover interrupted staging and reclaim unreachable objects under store locks while honoring revision and provider leases |

`RepositoryOpenTarget` contains the source and repository-store identities, immutable or
filesystem subject, requested ref, full resolved object ID when applicable, initial
logical path, optional line selection, optional provider target, trust profile, and a
subject lease. It never contains a provider response or credential.
The server receives this value before startup; a future chooser may produce the same
value and pass its subject to the source-session lifecycle.

GitHub URL syntax is implemented in the GitHub provider plugin, not in `cache/urls.py`.
The core dispatcher asks installed, trusted provider reducers for an ordinary clone
source plus `RepositorySelection`; the cache never branches on a GitHub object kind.
The provider plan names the manifest and loader changes that register this reducer.

### Tests and parity files

| Surface | Files |
| --- | --- |
| Formats, permissions, migration, identity, publication | `tests/test_cache_records.py`, `tests/test_cache_layout.py`, `tests/test_cache_permissions.py`, `tests/test_cache_identity.py`, `tests/test_cache_acquire.py` |
| URL and ref selection | `tests/test_cache_urls.py`, `tests/test_cache_selection.py`, GitHub reducer tests in the provider plugin |
| Immutable revision lifecycle | `tests/test_git_tree_source.py`, `tests/test_cache_repository_store.py`, `tests/test_cache_service.py`, subject-replacement cases in `tests/test_inventory_contract.py` |
| CLI behavior | `tests/golden/cli-cache-layout.tryscript.md`, `cli-cache-acquire.tryscript.md`, `cli-github-repo-open.tryscript.md`, `cli-github-branch-open.tryscript.md` |
| Registered surfaces | `devtools/check_parity.py`, `docs/project/architecture/arch-views-models-routes.md`, `tests/test_views_models_routes.py` |
| Installed artifact | `tests/test_distribution_policy.py` plus the existing isolated-wheel smoke test in `make verify` |

Every filename above is a delivery coordinate, not permission to create an abstraction
before its consumer.
A phase adds only the modules and callables it exercises through a test, route, or
user-visible open path.

## Phased Implementation Plan

### Phase 0: Design evidence and contract freeze — v0.11.0 entry point

- [ ] Remeasure full, blobless, and blobless-plus-backfill acquisition against the
  v0.10.0 history session, commit detail, comparison manifest, deferred patches,
  revision content, and canonical path-identity routes.
- [x] Review upstream through v0.8.0 and remove assumptions superseded by shipped Git
  history, revision, and diff infrastructure.
- [x] Review SoftSchema v0.7.0 and its enforced-composition boundary; install its Codex
  skill for future implementation turns.
- [x] Separate generic cache delivery, cache operations, chooser, GitHub modeling,
  GitHub acquisition, provider views, stack projections, and large-repository work.
- [ ] Freeze the safe URL grammar, source identity, slug, lock, staging, publication,
  quarantine, and trash state machines as fixtures.

### Phase 1A: Format foundation — infrastructure PR

This phase produces no user-visible result and stands between the goal and the first
repository that opens, so its scope is stated rather than assumed.

**Not negotiable**, because each one is what makes an interrupted or concurrent
operation safe rather than corrupting: source identity, atomic publication with a
no-replace rename, application-home locking, honest recorded state, `CACHEDIR.TAG`, the
`staging`/`trash` reclamation sweep, and compiled-schema drift checking.
A cache without these is not a smaller cache; it is one that loses entries.

**Deferrable if the phase proves too large to land in one step**, because each only pays
off once a *second* reader exists — that is, once a released version must read entries
another version wrote: the sequential migration harness and the ordered format history
beyond recording `f01`.

Drift checking is **not** deferrable, though an earlier draft listed it here.
Drift is a single-release failure: a packaged schema silently diverging from its model
weakens `status: enforced` the moment it happens, with no second reader required.
Dropping it would reopen exactly the hole the
[2026-08-26 design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
closed when it required both a compiled schema and a strict model.
The strict Pydantic models stay either way; it is the portable-schema and migration
machinery around them that can follow.

Deferring any of those is a decision to record in this plan with its reason, not a
silent trim. The argument against deferring is real and should be weighed each time: a
cache is released data from its first write, and retrofitting migration under entries
that already exist costs more than building it first.

- [ ] Add the application-home resolver, `config.yml`, `cache/layout.yml`, format
  history, future-format failure, and sequential migration harness.
- [ ] Adopt the exact released SoftSchema package after dependency and lock review;
  verify the `frontmatter-format` minimum and artifact hashes against released package
  metadata; record its `jlevy` first-party exemption and reviewed predecessor in
  *Audited First-Party Exceptions*; register the config, layout, repository-source,
  repository-store, and store-state contracts.
- [ ] Package deterministic compiled schemas and add compile-drift, corpus-validation,
  schema-inventory, and installed-wheel checks.
- [ ] Add atomic YAML reads/writes, application-home locking, quarantine, and
  recoverable-trash primitives without cloning or serving a URL.
- [ ] Enforce owner-only application-home paths (`mb-xa0p`) and refuse remote writes
  through symlinked, foreign-owned, or permissive cache ancestors.
- [ ] Freeze the lock hierarchy: home for layout/global enumeration, source alias for
  alias publication, repository stores in ascending ID order for ref/object publication
  and leases, then provider/resource for provider publication; never hold one across
  network work.
- [ ] Write `CACHEDIR.TAG` when the cache root is created, and add the startup
  `staging/`/`trash/` reclamation sweep, so no released phase accumulates unreclaimed or
  backed-up cache data.
- [ ] Prove config preserves unknown settings while machine records reject unknown
  fields and cache-controlled schema paths cannot redirect validation.
- [ ] Add the read routes `/api/cache/layout`, `/api/cache/sources`,
  `/api/cache/source/{slug}`, and `/api/cache/stores`, projecting the records above, and
  pin them with a golden through `metab --api`.

That last item is the one most likely to look like it belongs in a later phase, and it
does not.
It is what makes every subsequent behavior in this plan assertable: without it,
the state machine that Phase 1A exists to build is observable only by reading the
sandbox by hand. It is cheap here, because the records it projects are being written in
this phase anyway, and it satisfies the state clause in
[CLI parity](../done/plan-2026-08-21-cli-parity-and-golden-coverage.md).

The routes project **logical** state only — identity, format, publication state, head
revision. Never a directory listing: pack file names, object counts after `gc`, and
`.git` internals are not stable across runs, and a golden that asserted them would fail
for reasons that have nothing to do with this plan.

`metab --api` (`mb-ian3`) and the persisted-state parity clause have landed, so this
phase uses them directly rather than building a parallel inspection harness.
See [CLI-first delivery](plan-2026-08-28-cli-first-delivery-map.md).

### Phase 1B: Generic Git cache and repository URL open

This phase lands in five additive slices.
Each can merge with its own records, routes, goldens, and recovery behavior before the
next slice begins.

#### Phase 1B-a: Acquire and reuse a shared repository store (`mb-h51g`, `mb-dg00`)

- [ ] Add conservative source normalization, full identity digest, readable uniquified
  slug, collision verification, and source-alias locking.
- [ ] Extend `git/process.py` with version detection, `stdin=DEVNULL`, non-interactive
  environment controls, and explicit acquisition/background policies.
- [ ] Enforce the acquisition, blobless, and `git backfill` floors from
  [Git version gates](#git-version-gates); select full clone before publication when any
  is unmet, and return a typed `unsupported_git_version` state below the acquisition
  floor.
- [ ] Acquire a worktree-free Git database in same-filesystem staging, resolve and pin
  the default full object ID, and validate records, objects, and refs.
  Publish the immutable store first; atomically create the source alias last as the
  visibility commit. Reclaim or quarantine a completed orphan store after interruption
  between the commits.
- [ ] Reuse a valid cache hit without network access, provider detection, or credential
  lookup, including against an application home the process cannot write.
- [ ] Start measured object backfill only after serving; persist honest partial,
  backfilling, complete, and failed states.
- [ ] Apply the Phase 0 lazy-fetch decision on every read path, and prove a
  not-yet-backfilled blob read behaves as decided both online and offline.
- [ ] Force the untrusted profile for URL-opened roots once `mb-vib1` lands; until then
  acquisition, identity, publication, and CLI inspection may ship, and serving may not.
- [ ] Add CLI goldens and docs for first open, cache hit, offline reuse, unsafe input,
  interrupted clone, read-only application home, unsupported Git version, and repair
  guidance.

Acquisition staging and publication do not depend on the Git-status `is_clean` predicate
because the store has no working tree.
Git-status remains relevant only to an attached user filesystem subject; store
replacement, repair, and purge use object, ref, record, and lease validation instead.

#### Phase 1B-b: Introduce the content-source boundary (`mb-3bna`, `mb-tsdc`)

- [ ] Add `RepositorySubject`, `SourceSession`, `SourceCapabilities`, `ContentHandle`,
  and `ContentSource`, with one active attached-filesystem subject per server/browser
  session and generation-keyed replacement.
- [ ] Generalize inventory coordination, file/raw/tree/container delivery,
  classification, KPress, events, route caches, and plugin dispatch without changing
  filesystem behavior.
- [ ] Add bounded content-reader plugin calls.
  Keep `resolve_path` and `served_root` filesystem-only and capability-gate legacy hooks
  on a non-filesystem subject.
- [ ] Return typed unsupported capability results for recency, ignore state, watchers,
  activity, and mutation rather than fabricating values.
- [ ] Update built-in binary, structured, agent-log, diff, image, and Markdown hooks,
  route parity, and goldens; independently review and publish through `mb-tsdc`.

#### Phase 1B-c: Serve immutable Git revisions (`mb-z335`, `mb-hoae`)

- [ ] Add `AttachedWorktreeTarget` and `RepositoryStoreTarget` to the one Git process
  boundary, preserving fixed arguments and ambient-environment scrubbing.
- [ ] Pass the target and exact subject OID through repository discovery, history, refs,
  commit detail, comparisons, and Git diff adapters; do not infer immutable content from
  ambient `HEAD`.
- [ ] Define byte-segment `GitPath` identity and its lossless URL/display codec; use it
  across tree/file routes, diffs, anchors, and provider selections without constructing
  a host `Path`.
- [ ] Enumerate byte-safe full-OID trees and read bounded blobs through owned batch Git
  reader actors. Preflight size, serialize requests, drain frames, and restart after
  cancellation or protocol failure; implicit promisor fetch is disabled.
- [ ] Create or reuse a `GitRevisionSubject` keyed by repository-store identity and full
  object ID; validate tree availability before subject publication.
- [ ] Hold a cross-process shared maintenance lock for each live subject and durable
  private refs for offline-promised OIDs; GC, repack, and reclamation require the
  exclusive lock.
- [ ] Define symlink, gitlink, LFS-pointer, oversized-blob, promisor-miss,
  invalid-UTF-8, and newline-name behavior and pin each with focused tests.
- [ ] Prove two processes share one object store while browsing different OIDs without a
  checkout, index, local branch, or working-tree mutation.
- [ ] Independently review and publish through `mb-hoae` before any URL route claims it
  can serve a repository.

#### Phase 2A: Open repository and hosted web URLs (`mb-12cz`, `mb-ew38`, `mb-innz`)

- [ ] Add the trusted installed-plugin `ProviderUrlReducer` registration point; keep
  operator-directory plugins JavaScript-only and keep provider syntax out of cache
  identity and records.
- [ ] Require declared scheme/host claims plus `NotApplicable`, `Reduced`, and terminal
  `Rejected` outcomes; refuse duplicate or overlapping claims before startup.
- [ ] Change the CLI root boundary from `Path | None` to `str | None`; preserve URL
  bytes until classification and keep path-only modes receiving resolved paths.
- [ ] Reduce provider web URLs to a clone URL plus a selection record: the shapes in the
  variants table, line and column anchors, `?plain=1`, dropped tracking and display
  parameters, reserved-namespace refusal, and configurable Enterprise hosts.
- [ ] Open a repository-root URL through `resolve_open_target`, reuse the repository
  store without a network or provider credential lookup, and pass one immutable subject
  to server and inspection paths.
- [ ] Preserve a pull-request number as an optional provider target even before a
  provider adapter can hydrate it.
- [ ] Independently review and publish the URL-open slice through `mb-innz` on the exact
  green immutable-source head.

#### Phase 2B: Provider jobs and selected refs (`mb-jlon`, `mb-bf94`)

- [ ] Keep `selection.py` pure.
  Put `fetch_selected_ref`, `request_ref_fetch`, progress, cancellation, and typed stage
  outcomes in `jobs.py` behind the provider-neutral object job port.
- [ ] Key jobs by store, source, closed `FetchAuthorizationContext`, fetch-policy
  version, and exact refspec.
  Anonymous and proven provider-principal contexts may coalesce only on exact key
  equality; unknown SSH or credential-helper principals use a fresh unshareable context.
- [ ] First move `AuthorizationContextRef`, `authorization_context_key`,
  `LocalObjectAvailability`, and `LocalGitObjectAvailability` from
  `builtin_plugins/hosted_review/models.py` into `provider_resources/models.py`, keeping
  one key implementation, so core never imports a domain plugin.
  The selected-ref service reports local object state with those two types; the
  observation-guarded `local_git_object_availability` and
  `local_merge_commit_availability` constructors stay in the hosted-review plugin.
- [ ] Make `ProviderPrincipal` carry provider kind, instance, stable opaque principal,
  optional visibility-partition digest, and the derived authorization-context key.
  At the single `RepositoryObjectJobPort` boundary, validate an
  `AuthorizationContextRef` mode and field combination, derive its key, map it once to
  the internal variant, and reject an invalid record before job lookup; never accept a
  caller-supplied key.
  Provider or visibility-partition differences never coalesce merely because host,
  principal, source, and refspec match.
- [ ] Keep job identity separate from credential execution.
  Define `GitFetchCredentialLease` as an unforgeable, process-local, non-serializable
  handle into a core `GitFetchCredentialLeaseRegistry`, and let
  `RepositoryObjectJobPort.request_selected_refs` accept it only alongside the matching
  non-secret context. `validate_git_fetch_credential_lease` reads provider, instance,
  stable principal, authorization-context key, visibility partition, expiry, revocation,
  cancellation generation, and exact credential-free HTTPS sources from the registry
  entry, never from the handle, for every request before job lookup, including one that
  joins in-flight work.
  A provider-principal Git run uses the starting request’s lease; when that request
  cancels or its lease is revoked, core restarts the run once under another attached
  live lease for an equal authorization-context key or fails the remaining requests with
  a typed error. Leases authorize a context key, not a broker session.
  Prove the protocol with a test issuer.
  Until the Phase 3A askpass projection exists, a provider-principal request with a
  valid lease fails with `git_credentials_unavailable` before Git starts, so no ambient
  credential can be used.
  The broker and projection arrive in Phase 3A under the isolation rules in
  [Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md#fetch-jobs-authorization-and-credentials).
- [ ] Fetch into an isolated temporary repository or, for jobs without provider
  credentials, a quarantine with no lock held; persist a non-secret `StagedFetch`, then
  validate object format, expected full OID, source, auth-context kind, refspec, and
  base generation before compare-and-swap publication under the repository-store lock.
- [ ] Keep provider schemas, `gh`, auth, catalog, chooser, purge, and automatic eviction
  out of this phase. Never mutate an attached checkout or treat its remote as shared
  authority.
- [ ] Prove cancellation, same-key coalescing, unknown-principal non-coalescing,
  force-push/no-regression races, fork-source isolation, attached-checkout non-mutation,
  forged or unregistered handles, context/lease mismatch, expiry, revocation, and
  cancellation for starting and joining requests, and the pre-Git refusal of
  provider-principal work with focused tests and goldens.
  Assert that the opaque capability, ref names, staged records, and diagnostics contain
  no secret.
- [ ] Independently review and publish through `mb-bf94` on the exact green Phase 2A
  head before selected-branch or PR work consumes the service.

#### Phase 2C: Open any selected branch as an immutable revision (`mb-2xq7`, `mb-9aku`)

- [ ] Resolve the ambiguous ref/path split after acquisition against local heads,
  remote-tracking refs, tags, and full object IDs, longest matching prefix first.
- [ ] Have `selection.py` return a typed request for an explicitly missing remote ref;
  `jobs.py` owns the bounded network fetch and distinguishes missing, unauthorized,
  deleted, offline, and over-bound outcomes.
- [ ] Reuse the already published `GitRevisionSubject`; this slice adds moving-ref
  selection and bounded missing-ref acquisition, not another content representation.
- [ ] Add URL-reduction goldens for every row of the variants table, both fragment and
  query tables, a slash-containing branch name, a tag rather than a branch, the
  `raw.githubusercontent.com/.../refs/heads/<branch>/...` spelling, a ref that is not
  the pinned revision, a reserved namespace, and a pull-request URL whose provider
  target is retained.
- [ ] Add `cli-github-repo-open` and `cli-github-branch-open` goldens covering default,
  non-default, slash-containing, cached-offline, unavailable, and concurrently leased
  branches.
- [ ] Independently review and publish selected-branch integration through `mb-9aku` on
  the exact green provider-job head.

### Later: Generic catalog, refresh, and cache management

Phase 2B ships the provider-facing job lifecycle and selected-ref fetching needed for
v0.11.0. The operations below build on that service but remain outside the initial
vertical slice.

- [ ] Scan validated identity/state pairs into one provider-neutral catalog.
- [ ] Add list, inspect, Git-only refresh, repair diagnostics, and recoverable purge.
- [ ] Fetch and prune Metabrowser-owned refs without changing an existing subject;
  publish only verified ref/object pairs and retain objects leased by live subjects.
- [ ] Add coordinated job progress, cancellation, stage outcomes, and process-safe races
  among open, refresh, promote, repair, and purge.
- [ ] Add size accounting, including quarantined and staged bytes; select no automatic
  eviction policy until measured usage justifies one.
  `CACHEDIR.TAG` and the reclamation sweep already landed in Phase 1A.

### Later: Repository chooser and session switching

- [ ] Add a chooser over the generic catalog with recent, favorite, offline, partial,
  dirty, and refresh states.
- [ ] Make root selection session-scoped rather than mutating global settings.
- [ ] Route every root replacement through one lifecycle boundary that closes the old
  inventory handle, history sessions, activity tracking, subscriptions, and retained
  response and client caches before the new root becomes visible.
- [ ] Preserve each repository’s selected path, Git scope, and revision-navigation state
  as bounded client state.
- [ ] Measure warm-cache first paint and choose eager, prefetched, or on-demand asset
  tiers from observed cost.

### Later: Measured very-large-repository support

- [ ] Revisit shallow plus progressive deepening only for repositories whose measured
  acquisition cost justifies the added state model.
- [ ] Mark truncated history and disable blame while `.git/shallow` exists.
- [ ] Coordinate deepening with unbounded-history session design instead of adding a
  second pagination model.

## Phase Dependency Map

| Phase | Depends on | Does not depend on | User-visible result |
| --- | --- | --- | --- |
| v0.11 start (`mb-xxhi`) | v0.10.0 release (`mb-i57d`) | Design and review | Implementation starts from the released `main` commit |
| 1A format foundation | Release gate, Phase 0 contract decisions | GitHub, chooser | Versioned app home and strict cache records |
| 1B-a generic Git cache | 1A | Git-status clean predicate, GitHub, chooser, serving | Any supported clone URL publishes or reuses one shared worktree-free store |
| 1B-b source boundary (`mb-3bna`, `mb-tsdc`) | 1B-a | GitHub, provider API, immutable Git content | Filesystem serving runs through one capability-aware source session |
| 1B-c immutable source (`mb-z335`, `mb-hoae`) | 1B-b | GitHub, provider API, chooser | Concurrent full-OID trees and blobs open without a checkout or shared index |
| Untrusted-content profile (`mb-cun0`, `mb-vib1`, `mb-d658`) | 1B-c for publication; implementation is independent | Cache, GitHub, provider API | Fetched content is served only under the sandboxed untrusted profile |
| 2A repository URL open (`mb-12cz`, `mb-ew38`, `mb-innz`) | Untrusted-content profile layer, provider URL-reducer SDK | Provider API or schemas | Any supported repository URL opens an immutable revision subject |
| 2B provider-job foundation (`mb-jlon`, `mb-bf94`) | Green 1B-a acquisition and 2A URL-open PRs | Full catalog, chooser, purge | Independently reviewed provider jobs and selected-ref fetching for branches and GitHub |
| 2C selected branch (`mb-2xq7`, `mb-9aku`) | Green 2B provider-job PR | Provider API or schemas | Any exposed and authorized branch opens at its resolved immutable revision |
| Later cache operations | Phase 2B jobs | Provider support | Generic list, inspect, refresh, and purge |
| Later chooser | Generic catalog | GitHub | Instant switching among cached repositories |
| Later large repositories | Measurements from 1B and real use | Provider support | Explicit bounded behavior for exceptional repository scale |

Two dependencies leave this plan, and they leave in opposite directions.

**Inbound:** the release gate (`mb-i57d` → `mb-xxhi`) blocks every v0.11 implementation
bead so work begins from released `main`. Git-status Phase 1 (`mb-u4mf`) owns local
working-tree semantics but does not gate integrity or serving of the worktree-free
repository store.
The content-trust chain (`mb-cun0` → `mb-vib1`, published by `mb-d658`)
blocks URL serving in 2A and 2C, but not format, acquisition, or immutable-source tests.
Those tracks can proceed independently after the release gate.

**Outbound, depending on the extracted Phase 2B selected-ref foundation:**
[the GitHub provider plan](plan-2026-08-27-github-provider-and-pull-requests.md) needs a
stable source attachment, shared repository-store service when content is requested,
atomic publication, the documented lock hierarchy, owner-only storage, job progress and
cancellation, and core-side ref fetching.
Provider metadata for a user-owned checkout does **not** require a published Git store,
catalog, chooser, purge, or size accounting.
That extracted Phase 2B service is `mb-jlon`; the full generic catalog and management
phase remains `mb-0ybg` and no longer blocks GitHub acquisition.

The Git-status `is_clean` predicate applies only to an attached user filesystem subject.
It does not gate acquisition, serving, replacement, repair, or purge of a worktree-free
repository store because that store has no checkout or index to classify.
Store integrity instead verifies record generations, private refs, required object
reachability, leases, and publication markers.
Below Git 2.36 an attached subject reports `unsupported_git_version` rather than
inferring a clean working tree; immutable repository subjects remain available.

## Testing Strategy

The ordinary suite uses `file://` fixture repositories and an isolated
`METABROWSER_HOME`; it never requires the network or a real credential store.
There is no test-only transport override: `file://` is a production transport, so the
suite exercises the same acquisition path a user gets.

- **Format and migration:** old released config migrates stepwise and idempotently; a
  future layout or contract fails before mutation; config extensions survive; registry
  binding outranks document metadata; compiled schemas cannot drift.
- **Identity:** documented equivalent URL syntax reuses one entry; preserved
  distinctions do not; forced short-digest collisions extend the slug; query, fragment,
  credentials, controls, and unsafe transports fail before Git.
- **Publication:** interruption at every staging boundary leaves no visible incomplete
  source; the store publishes before the alias visibility commit; a crash between them
  leaves only a reclaimable orphan; source, state, refs, and resolved object IDs agree
  before publication; a cache hit needs no network.
- **Read-only behavior:** browse and ref refresh create no checkout or index and never
  modify an attached user working tree or `.git` state.
- **Concurrency:** two processes share one completed store while browsing different
  object IDs; source/auth-incompatible fetches do not coalesce; a slower staged fetch
  cannot regress a newer ref generation; open, refresh, migration, repair, and purge
  cannot race across processes.
- **Credential capabilities:** a provider-principal fetch starts only with a registered,
  matching, live, source-bounded lease handle, validated from the registry for starting
  and joining requests alike; forged, unregistered, missing, expired, revoked,
  source-mismatched, host-mismatched, provider-mismatched,
  authorization-context-mismatched, visibility-partition-mismatched, and
  principal-mismatched leases produce typed failures without consulting ambient Git
  authentication. Before Phase 3A such a request fails before Git starts.
  In Phase 3A, a `.netrc` login, SSH agent, trace variable, credential helper,
  `insteadOf` rewrite, extra header, or template or repository-local configuration
  cannot supply, print, store, or reroute the credential, and a cross-host redirect
  fails typed. Provider-kind and visibility-partition changes produce distinct job keys.
  Secrets cannot enter argv, ordinary child environment, diagnostics, files, staged
  records, refs, or job identities.
- **Git integration:** immutable subjects satisfy history, direct revisions, commit
  summaries, bounded tree/blob reads, and diff rendering before and after backfill.
- **Revision subjects:** default and non-default branches, slash-containing names, tags,
  and full object IDs resolve to immutable OIDs; leases reuse the store and batch
  readers; missing/offline refs fail honestly; no case creates a worktree or moves a
  local branch.
- **Content capabilities:** immutable subjects expose no filesystem path, fake mtime,
  ignore state, watcher, activity, or mutation state; routes and legacy plugin hooks
  return the typed unsupported state or remain absent, while byte-oriented built-ins use
  the bounded content-reader port.
- **Git paths and blobs:** bytewise ordering and the `GitPath` wire codec round-trip
  invalid UTF-8 and newline names; symlinks are not followed, gitlinks are not folders,
  LFS pointers remain blobs, and oversized or missing objects fail before an unbounded
  body read. Cancellation or framing failure restarts the batch reader.
- **Leases and maintenance:** two processes hold shared maintenance locks while serving;
  GC, repack, and reclamation require the exclusive lock; crash release, durable refs,
  read-only cache hits, and Windows trash movement preserve every promised OID.
- **Subject lifecycle:** replacing a selected subject joins the old inventory and Git
  sessions, invalidates subject-owned server and browser caches, and prevents work from
  the old subject from publishing after the new subject is visible.
- **Trust:** URL roots receive the untrusted capability set, never serve `.git`, and
  cannot promote repository-local metadata to host config.
- **Parity:** every new route, model, persisted state, and user-visible functional
  aspect is registered and driven through the exact production path by a golden.
- **Provider contracts:** every valid fixture passes structural and semantic validation;
  every invalid fixture fails with a stable code and path; unknown provider enum values
  normalize without opening the record schema.
- **Provider snapshots:** every published manifest is structurally and semantically
  valid; a valid partial refresh may advance `current` with explicit partiality while
  preserving `last-complete`; a failed refresh advances neither pointer; deletion,
  permission loss, not-requested, and rate-limit outcomes remain distinct.
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
- Snapshot sharding and transport selection moved with
  [the provider plan](plan-2026-08-27-github-provider-and-pull-requests.md) and are
  deferred there rather than here.
- Automatic eviction waits for measured size data from later cache operations and
  remains absent unless a defensible default follows.
- A live session retains its immutable subject until explicit navigation; background
  refresh never switches its object ID silently.

## Acceptance Criteria for the First Usable Phase

The first usable repository URL and branch phases are complete when:

- `metab <any-common-repository-url>` publishes one validated source alias and shared
  worktree-free repository store, then serves an immutable subject with the untrusted
  profile;
- a `/blob/<ref>/<path>` URL opens that file at the full object ID resolved from
  `<ref>`, and `/tree/<ref>/<path>` opens that directory — a URL naming a file does not
  land at the repository root or a different revision;
- a non-default branch is served from a leased full-OID Git-tree subject while the
  shared store refs, other subjects, and local branches remain independent;
- a branch name containing slashes resolves against the cloned ref list rather than
  being guessed at parse time;
- repeating the command opens the cached subject without clone, fetch, provider
  detection, credential lookup, or network access;
- `source.yml` names one credential-free source identity, `store-alias.yml` attaches it
  to one shared store, and the store records name an observed default full revision and
  honest object state without a global active revision;
- browsing and Git ref refresh do not create or modify a working tree, shared index, or
  active session revision;
- interrupted and concurrent clones, an unsafe URL, future format, corrupt record,
  missing credential, unavailable network, and failed backfill each produce bounded and
  truthful outcomes;
- Files, Git history, direct revision, commit summary, and diff views work against the
  immutable content source under the same contracts as a local repository where the
  underlying facts are meaningful; and
- no GitHub API, provider credential, or provider schema is required, and core contains
  no GitHub-specific branch to satisfy any criterion above.

## References

- [Repository cache and open from a Git URL](../../research/research-2026-08-11-repo-cache-and-git-url-open.md)
  — acquisition measurements, prior art, and the dated research record
- [Repository-library and GitHub-model design review](../../reviews/review-2026-08-26-repository-library-and-github-model.md)
  — findings resolved by this rewrite
- [Git graph view](plan-2026-08-06-git-graph-view.md) — shipped Git history and the
  repository-root boundary
- [General diff rendering](plan-2026-08-17-general-diff-rendering.md) — shared
  comparison pipeline and its boundaries with durable acquisition and immutable revision
  subjects
- [Repository Sources and Provider Mirrors](../../architecture/arch-repository-sources-and-provider-mirrors.md)
  — shared Git store, attached checkout, provider mirror, and multi-client contract
- [Git revision navigation performance](../done/plan-2026-08-25-git-revision-navigation-performance.md)
  — current revision loading and comparison behavior
- [Unbounded virtualized Git history](../done/plan-2026-08-25-unbounded-virtualized-git-history.md)
  — future history continuation and virtualization
- [HTML rendering and trust model](plan-2026-08-06-html-rendering-and-trust-model.md) —
  untrusted-content dependency
- [tbd on-disk format versioning](https://github.com/jlevy/tbd/blob/v0.8.1/docs/tbd-format-versioning.md)
  — fail-closed layout formats and ordered migration publication
- [SoftSchema v0.8.1 guide](https://github.com/jlevy/softschema/blob/v0.8.1/docs/softschema-guide.md)
  — profiles, contract maturity, host registries, and artifact validation
- [SoftSchema v0.8.1 specification](https://github.com/jlevy/softschema/blob/v0.8.1/docs/softschema-spec.md)
  — portable YAML, enforced validation, schema binding, and compatibility rules

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
