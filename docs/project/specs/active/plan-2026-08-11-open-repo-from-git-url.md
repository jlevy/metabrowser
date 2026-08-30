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

- Accept any common repository URL anywhere the CLI currently accepts a root path: clone
  URLs, and provider web URLs reduced to the repository they name.
- Open what the URL pointed at, not merely the repository containing it — a `/blob/` URL
  opens that file, a line anchor selects those lines.
- Preserve the root argument as a string at the Click/Typer boundary, then classify it
  before any `Path` construction can rewrite URL syntax.
- Derive one stable cache identity from the credential-free clone source, and reuse the
  same entry on every later open.
- Publish repositories under `~/.metabrowser/cache/repos/<uniquified-slug>/gitroot` only
  after checkout and metadata validation complete.
- Keep the browsed working tree pinned and read-only from Metabrowser’s perspective.
  Fetching refs must not dirty or silently advance it.
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
  That gate is larger than one bead and is sequenced explicitly below — see
  [The gate that decides when this ships](#the-gate-that-decides-when-this-ships).
- Metabrowser already depends on Pydantic, JSON Schema, ruamel.yaml, PyYAML, and
  frontmatter-format. SoftSchema v0.7.0 is a first-party package over the same boundary,
  but adopting it also raises the frontmatter-format minimum from 0.3 to 0.4 — a claim
  Phase 1A verifies against the released package metadata rather than carrying forward
  from this plan. Phase 1A must review that upgrade, update `uv.lock`, and run the full
  supply-chain and distribution gates rather than treating the overlap as proof of
  compatibility.
- Being first-party does not by itself exempt SoftSchema from the release cool-off.
  [`SUPPLY-CHAIN-SECURITY.md`](../../../../SUPPLY-CHAIN-SECURITY.md) is explicit that
  first-party identifies the publisher and does not retire the threat the cool-off
  exists for, which is a compromised publishing account.
  What earns `get-tbd` its exemption is reach: nothing in the build, CI, test, or
  publishing path runs it, so a bad release costs a developer’s session.
  SoftSchema does not inherit that argument — it validates cache records on a runtime
  path, inside the shipped wheel, so a bad release reaches every user.
  Phase 1A therefore either adds a `softschema` row to *Audited First-Party Exceptions*
  with its own reviewed-against release and blast-radius statement, or applies the
  ordinary 14-day cool-off.
  It does not proceed on the overlap with existing dependencies.

The v0.8.0 revision click starts a comparison that needs blobs.
Blobless clone followed by background backfill remains the leading acquisition strategy,
but Phase 0 must remeasure the complete current route before promising a timing or
selecting a threshold between full and blobless acquisition.

## The Gate That Decides When This Ships

The single largest scheduling fact about this plan is not in this plan.

A fetched repository is third-party content, so serving one requires the untrusted
capability profile. That profile is `mb-vib1`, which is blocked by `mb-cun0` — sandboxed
`/raw` responses and same-origin proof on `/api`. Both are open `P1` tasks belonging to
[the HTML rendering and content-trust plan](plan-2026-08-06-html-rendering-and-trust-model.md),
which is `Status: Draft` with nothing implemented.

```text
mb-cun0  sandbox /raw, same-origin proof on /api
   └──► mb-vib1  capability set and --untrusted profile
           └──► mb-ew38  generic URL open and offline reuse
```

Two consequences, both worth stating plainly rather than discovering during
implementation:

- **Every estimate for this feature must include that chain.** The cache work alone does
  not produce a user-visible result; the first thing anyone can actually open is gated
  on a security workstream in another document.
- **The chain depends on nothing here.** `mb-cun0` and `mb-vib1` have no dependency on
  the cache, on Git status, or on each other beyond their own order, so they can proceed
  in parallel with everything in Phase 0 through 1A. Sequencing them alongside rather
  than after is what keeps the gate off the critical path.

This plan does not absorb that work or restate its design.
It records the dependency, names the beads, and treats “serving is gated” as a
scheduling fact with a shape rather than a footnote.

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

### Reclaiming `staging/`, `trash/`, and quarantine

Retaining data is the right default here, but retention without a reclamation rule is
how a cache silently becomes the largest directory in a home folder.
Each of the three gets its rule in Phase 1A, when the directories are created, rather
than in Phase 2 when someone notices the disk:

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
the retained path, so the directory is never a silent accumulation waiting for Phase 2’s
`--repo-inspect` to reveal it.

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

`last_opened_at` does mean that an otherwise offline, read-only cache hit still writes
to disk, so that write must not be able to fail the open.
A `state.yml` update that fails — read-only home, full disk, a lock held by another
process — is logged and the open proceeds against the validated `gitroot`. The
consequence of dropping it is a stale bookkeeping timestamp; the consequence of treating
it as fatal is refusing to serve a repository that is present, valid, and pinned.
Nothing in serving depends on `last_opened_at`, and the recency ordering it feeds is a
Phase 3 chooser affordance, not a correctness input.

This is a listed Phase 1B acceptance case, beside interrupted clone and unavailable
network: a cache hit against an application home the process cannot write must still
serve.

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
The separate [Git-status plan](plan-2026-08-26-git-status-and-working-tree-diffs.md)
defines the lossless status service and its `is_clean` predicate.
Cache integrity should call that predicate rather than keep a second porcelain parser or
a second definition of clean.

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

### What a selection can actually address

The selection is bounded by the URL grammar, and that boundary is narrower than the
table above suggests.

`/view/<path>` addresses the served tree; `/commit/<rev>[/<inner>]` addresses a change
set. **Neither addresses file content at an arbitrary revision**, and
[the grammar says why](../../../architecture.md#browser-url-grammar): a revision is not
a path in the served tree, so it gets its own route rather than a sigil inside `/view/`.

A selection therefore resolves to a real surface when `<ref>` resolves to the entry’s
pinned `active_revision` — the ordinary case, because acquisition pins the default
branch and that is the ref most pasted URLs carry.
When `<ref>` names some other branch, tag, or commit, Phase 1B opens the repository at
its pinned revision and reports which revision was requested and which is served.
It does not show another revision’s content under the requested path, which is the one
genuinely wrong outcome available here.

Line and column anchors have the same shape of limit: carried through the parse, applied
where the target view supports a line selection, and reported rather than silently
dropped where it does not.

Addressing content at an arbitrary revision is a real gap, and closing it is what a
content-at-revision route would do.
It is not in this phase and this plan does not promise it.
Opening the right repository at its pinned revision while saying so is bounded and
honest; promising a file at a ref nothing can render is not.

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

**Local origins, decided 2026-08-28.** `cache/urls.py` classifies transport as `https`,
`ssh`, or `local`, and `file://` URLs and local repository paths are accepted as Git
sources.
`acquire` binds a `local` source to the untrusted profile unconditionally, which
is where a source nobody authenticated belongs anyway.

This is a widening of an earlier HTTPS-and-SSH-only rule, and the reason is worth
stating plainly. The grammar exists to reject input that is ambiguous or dangerous —
credentials, query, fragment, option-like strings, remote helpers — not to rank
transports by trust.
A path on the local filesystem is strictly safer than either transport already allowed:
no network, no credentials, no name resolution.
It also serves a real workflow in mirrors and air-gapped checkouts.

The decision is load-bearing for testing, which is the honest reason it came up.
Acquisition goldens clone from a local origin built in the same sandbox, so they run the
real `run_git` on the real code path with no network and no mocking.
The alternative considered and rejected was a test-only escape hatch admitting local
origins, which would fork production and test logic — the thing
`tbd guidelines golden-testing-guidelines` warns against most directly, and which would
mean the acquisition path proved by CI was not the acquisition path users run.
Web-URL reduction runs before this gate, not around it: its output is a clone URL that
passes through exactly the same transport allowlist, credential rejection, and option
screening as one the user typed.

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
uses SSH batch mode, and disables submodule recursion, hooks, automatic maintenance,
unsafe transports, and symlink materialization.

A cache hit validates the entry and serves its existing `gitroot` without fetch,
credential lookup, or background refresh.
This rule is observable and tested.
A failed backfill leaves the published entry usable and honestly marked partial; it does
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
   there is never a published entry whose reads can reach the network unexpectedly.
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
detected string is recorded in `repository.yml` under `acquisition.git_version` so a
later entry can be explained.

Separately from these capability floors, acquisition requires a Git release carrying the
fixes for the known clone-time vulnerabilities in submodule handling and symlinked
`.git` directories.
That floor tracks upstream advisories rather than a feature, so Phase
0 pins the exact version alongside the transport allowlist and records it beside this
table; it is not satisfied by 2.26 alone.

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

## Provider Support Lives in Its Own Plan

GitHub modeling, acquisition, snapshot storage, views, and pull-request stacks moved to
[the GitHub provider plan](plan-2026-08-27-github-provider-and-pull-requests.md).
That document owns the record families, the storage layout, and the acquisition
boundary.

What stays here is the part the generic cache owes a provider, and it is deliberately
small: a published entry with a stable identity, atomic publication, application-home
locking, job progress and cancellation, and core-side Git ref fetching on request.
Core allocates a provider namespace under an entry and does nothing else
provider-specific — it does not import a provider schema, branch on a provider object
kind, or let provider state affect generic identity, refresh, or purge.

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
- [ ] Adopt the released SoftSchema package after dependency and lock review; verify the
  `frontmatter-format` minimum against released package metadata; record the
  supply-chain decision as an *Audited First-Party Exceptions* row with a blast-radius
  statement or apply the ordinary cool-off; register the config, layout, repository
  identity, and repository state contracts.
- [ ] Package deterministic compiled schemas and add compile-drift, corpus-validation,
  schema-inventory, and installed-wheel checks.
- [ ] Add atomic YAML reads/writes, application-home locking, quarantine, and
  recoverable-trash primitives without cloning or serving a URL.
- [ ] Write `CACHEDIR.TAG` when the cache root is created, and add the startup
  `staging/`/`trash/` reclamation sweep, so no released phase accumulates unreclaimed or
  backed-up cache data.
- [ ] Prove config preserves unknown settings while machine records reject unknown
  fields and cache-controlled schema paths cannot redirect validation.
- [ ] Add the three read routes — `/api/cache/layout`, `/api/cache/entries`, and
  `/api/cache/entry/{slug}` — projecting the records above, and pin them with a golden
  through `metab --api`.

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

This phase now depends on `metab --api` (`mb-ian3`) landing first, so that its proof is
a golden transcript rather than a parallel test harness written and then thrown away.
See [CLI-first delivery](plan-2026-08-28-cli-first-delivery-map.md).

### Phase 1B: Generic Git cache and URL open — first usable feature PR

- [ ] Change the CLI root boundary from `Path | None` to `str | None`; preserve URL
  bytes until classification and keep path-only modes receiving resolved paths.
- [ ] Add conservative source normalization, full identity digest, readable uniquified
  slug, collision verification, and per-source locking.
- [ ] Reduce provider web URLs to a clone URL plus a selection record: the shapes in the
  variants table, line and column anchors, `?plain=1`, dropped tracking and display
  parameters, reserved-namespace refusal, and configurable Enterprise hosts.
- [ ] Resolve the ambiguous ref/path split after acquisition against the cloned ref
  list, longest matching prefix first, falling back to the repository root with an
  explicit unresolved-selection report.
- [ ] Extend `git/process.py` with version detection, `stdin=DEVNULL`, non-interactive
  environment controls, and explicit acquisition/background policies.
- [ ] Enforce the acquisition, blobless, and `git backfill` floors from
  [Git version gates](#git-version-gates); select full clone before publication when any
  is unmet, and return a typed `unsupported_git_version` state below the acquisition
  floor.
- [ ] Clone to same-filesystem staging, resolve and pin HEAD, validate records and
  checkout, and publish with no replacement.
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
- [ ] Add URL-reduction goldens for every row of the variants table, both fragment and
  query tables, a slash-containing branch name, a tag rather than a branch, the
  `raw.githubusercontent.com/.../refs/heads/<branch>/...` spelling, a ref that is not
  the pinned revision, a reserved namespace, and a pull-request URL that opens the
  repository while naming the object it cannot yet render.

### Phase 2: Generic catalog, refresh, and cache management

- [ ] Scan validated identity/state pairs into one provider-neutral catalog.
- [ ] Add list, inspect, Git-only refresh, repair diagnostics, and recoverable purge.
- [ ] Fetch and prune refs without changing `gitroot`; stage promotion separately and
  refuse to replace a live root.
- [ ] Add coordinated job progress, cancellation, stage outcomes, and process-safe races
  among open, refresh, promote, repair, and purge.
- [ ] Add size accounting, including quarantined and staged bytes; select no automatic
  eviction policy until measured usage justifies one.
  `CACHEDIR.TAG` and the reclamation sweep already landed in Phase 1A.

### Phase 3: Repository chooser and session switching

- [ ] Add a chooser over the generic catalog with recent, favorite, offline, partial,
  dirty, and refresh states.
- [ ] Make root selection session-scoped rather than mutating global settings.
- [ ] Preserve each repository’s selected path, Git scope, and revision-navigation state
  as bounded client state.
- [ ] Measure warm-cache first paint and choose eager, prefetched, or on-demand asset
  tiers from observed cost.

### Phase 4: Measured very-large-repository support

- [ ] Revisit shallow plus progressive deepening only for repositories whose measured
  acquisition cost justifies the added state model.
- [ ] Mark truncated history and disable blame while `.git/shallow` exists.
- [ ] Coordinate deepening with unbounded-history session design instead of adding a
  second pagination model.

## Phase Dependency Map

| Phase | Depends on | Does not depend on | User-visible result |
| --- | --- | --- | --- |
| 1A format foundation | Phase 0 contract decisions | GitHub, chooser | Versioned app home and strict cache records |
| 1B generic Git cache | 1A, untrusted-profile gate for serving, Git-status Phase 1 (`mb-u4mf`) for `is_clean` | GitHub API or schemas | Any supported clone URL opens or reuses one local read-only entry |
| 2 cache operations | 1B | Provider support | Generic list, inspect, refresh, and purge |
| 3 chooser | 2 catalog | GitHub | Instant switching among cached repositories |
| 4 large repositories | Measurements from 1B and real use | Provider support | Explicit bounded behavior for exceptional repository scale |

Two dependencies leave this plan, and they leave in opposite directions.

**Inbound, blocking 1B:** the content-trust chain (`mb-cun0` → `mb-vib1`) gates serving,
and Git-status Phase 1 (`mb-u4mf`) owns the `is_clean` predicate.
Neither depends on anything here, so both can run alongside Phase 0 and 1A rather than
after them.

**Outbound, depending on 2:**
[the GitHub provider plan](plan-2026-08-27-github-provider-and-pull-requests.md) needs a
published entry with a stable identity, atomic publication, application-home locking,
job progress and cancellation, and core-side ref fetching.
It does **not** need the catalog, the chooser, purge, or size accounting.
If provider work is scheduled before the rest of Phase 2, the job lifecycle and ref
fetching are a small extraction that can be delivered ahead of it.

The `is_clean` dependency is worth restating because it is a hard ordering constraint
rather than a convenience: Phase 1B on Git-status Phase 1 (`mb-u4mf`), which owns the
`is_clean` predicate cache integrity calls.
It is a hard ordering constraint rather than a convenience: landing 1B first would leave
integrity either unchecked or served by a second porcelain parser, which is the outcome
both plans exist to prevent.
The dependency is recorded in the bead graph as well as here, because a constraint that
lives only in prose is one nobody is reminded of.

Below Git 2.36 the status service reports `unsupported_git_version`, so the predicate is
absent and cache integrity reports its check as unavailable rather than inferring clean.

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
- **Read-only behavior:** browse and ref refresh leave the shared Git-status service’s
  clean predicate true and `active_revision` unchanged; an externally dirtied entry is
  reported rather than reset.
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
- Snapshot sharding and transport selection moved with
  [the provider plan](plan-2026-08-27-github-provider-and-pull-requests.md) and are
  deferred there rather than here.
- Automatic eviction waits for Phase 2 size data and remains absent unless a defensible
  default follows.
- A live session either retains its pinned root until reopen or explicitly accepts a
  staged replacement; background refresh never switches it silently.

## Acceptance Criteria for the First Usable Phase

Phase 1B is complete when:

- `metab <any-common-repository-url>` publishes one validated entry under
  `~/.metabrowser/cache/repos/<uniquified-slug>/gitroot` and serves it with the
  untrusted profile;
- a `/blob/<ref>/<path>` URL whose `<ref>` resolves to the pinned revision opens that
  file, and `/tree/<ref>/<path>` opens that directory — a URL naming a file does not
  land at the repository root;
- a `<ref>` resolving to any other revision opens the repository at its pinned revision
  and names both, rather than showing another revision’s content at that path;
- a branch name containing slashes resolves against the cloned ref list rather than
  being guessed at parse time;
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
