# Feature: Repository Library and Open from a Git URL

**Date:** 2026-08-11 (rewritten 2026-08-26; refreshed 2026-09-16)

**Author:** Joshua Levy (with LLM assistance)

**Status:** Shared-store design correction under review; Phase 0 contracts frozen
2026-09-16; v0.11.0 implementation is release-gated

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
  Network work begins only for a missing entry, an explicit refresh, or an explicit
  object fetch; Git reads never fetch implicitly (see
  [the offline guarantee](#blobless-acquisition-and-the-offline-guarantee)).
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
Phase 0 remeasured every route against full, blobless, and converged stores and chose
blobless acquisition with an explicit prefetch of the default revision and background
convergence through explicit object-ID fetches, not `git backfill`; see
[Phase 0 decisions](#phase-0-decisions).

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

Repository and provider cache content may be private, so everything Metabrowser keeps
under the application home is reachable only by the user running it.
`metabrowser.home` enforces this, and cache and provider code create or open
application-home paths only through it; its module docstring gives the threat each rule
answers.

- `ensure_private_directory(home, relative_path)` creates or verifies a directory.
- `open_private_file(home, relative_path, flags)` opens or creates a file and returns a
  descriptor.
- `validate_private_home(home)` checks the home and its ancestors without changing
  anything.

Every refusal is a `PrivateStorageError` with a violation, a logical location, and a
path-free message naming a remedy.
The path stays on the exception for local logs, and any other `OSError` leaves these
functions without file names.

**Above the home.** Each directory the kernel traverses to reach the home must belong to
root or the current user.
It may be readable by anyone, but it must not give another principal write access: no
group or other write bit unless it is sticky, and on macOS no ACL allow entry granting
another principal a write-class right.
A symbolic link there is followed only when root or the current user owns it, and each
directory it leads through is checked the same way, so `/home` pointing into `/var/home`
works and a planted link does not.
Nothing above the home is ever modified.

**The home.** The home must be a real directory the current user owns, with no group or
other mode bits and, on macOS, no ACL allow entry for another principal.
Deny entries, such as the `group:everyone deny delete` on an ordinary macOS home, are
accepted. An existing home that fails is refused, never repaired, so an explicit
permissive `METABROWSER_HOME` receives an actionable refusal rather than a private
write. A missing home is created by path under its verified parent, then set to `0700`
and stripped of inherited ACL entries while it is still empty.

**Below the home.** An entry is private when it has no group or other permission bits
and no ACL allow entry for another principal.
Any owner-only mode passes: Git child processes run with umask `077`, so a store holds
`0700` directories and `0400` or `0600` files, and none of them needs repair.
Measured on Git 2.50.1: under umask `022` Git wrote `0755` directories and `0444` and
`0644` files, and `core.sharedRepository=0600` still left six of seven directories
`0755`; under umask `077` every directory was `0700` and every file `0400` or `0600`
([store modes](../../../../explorations/repository-cache/README.md#store-reads-and-file-modes)).
Entries Metabrowser creates itself are exactly `0700` directories and `0600` files from
creation, whatever the umask, with any inherited ACL entries removed before content is
written, and they are removed again if they are then refused.
Entries are reached by directory descriptor without following links and re-identified by
device and inode after opening.
A file must be a regular file with exactly one link.
It is opened non-blocking and without `O_TRUNC`, and truncated only after the descriptor
is verified. The chosen home is Metabrowser-owned by definition, so any entry below it
that the current user owns is repairable.
Repair removes only the group and other bits and a sharing ACL, with a logged warning;
it never adds owner permissions, so an entry whose own mode denies its owner the access
requested is refused.
A symbolic link, a foreign-owned entry, or a hard-linked file is refused and left
unchanged.

**Repair is not revocation.** Tightening an entry affects later opens only; a descriptor
or directory handle opened while the entry was shared stays usable.
Directories and read-only file opens are therefore repaired, but opening a file for an
in-place write is refused when its mode or ACL shared it.
Record writes create a temporary file with `O_CREAT | O_EXCL` in the target directory
and rename it into place.
A lock file that was ever shared is replaced only after its old file’s lock is acquired
without blocking: the replacement is created and renamed into place, and then the old
lock is released.
If the old lock cannot be acquired the file is refused, because another
holder may still have it locked, and renaming a new file over it would let a second
holder acquire the same lock.

**Unverifiable is refused.** A file system that does not keep modes, an ACL that cannot
be read or interpreted, and a platform without descriptor-relative, no-follow operations
all fail closed. Windows is such a platform today: every call refuses as `unverifiable`
until current-user-only ACL enforcement lands in `mb-pyqf`.

On Linux only mode bits are inspected, which is enough for POSIX ACLs: an object’s
group-class bits are its ACL mask, which bounds every named user and group entry, and a
mode without group or other bits clears both the mask and the `other` entry.
NFSv4 ACLs are not inspected.
Read-only browsing of an ordinary local path outside the application home performs none
of these checks, and attaching such a path to a provider mirror writes only below the
home.

### Lock order

Locks have disjoint scopes and one fixed order:

1. the application-home lock is used only for layout migration, global enumeration or
   sweeps, and moving quarantined entries to trash;
2. a source-alias lock protects alias creation and compare-and-swap repointing;
3. repository-store locks, acquired in ascending `RepositoryStoreId` order, protect
   store directory publication and removal, store records, and ref compare-and-swap; and
4. a provider/resource lock protects one binding, staged publication, current-pointer
   update, or provider reclamation operation.

No network work, provider process, or long-running Git process runs while any of these
locks is held. A job does its network work outside them, then acquires source-alias →
ordered repository stores → provider/resource as required, revalidates its generations,
expected object IDs, and authorization context, and publishes atomically.
The application-home lock is never acquired while holding either narrower lock.

Locks are BSD `flock` on lock files, never POSIX record locks: on the measured APFS home
a `flock` holder that was SIGKILLed released within 2.8 ms, while a `lockf` lock
vanished when its own process closed an unrelated descriptor for the same file
([measurements](../../../../explorations/repository-cache/README.md#platform-primitives)).
Every lock file lives under `cache/locks/`, never inside a directory that publication,
purge, quarantine, or reclamation renames, and a holder compares the locked descriptor’s
`fstat` with the path’s `lstat` after acquiring and retries on a mismatch, because a
sweep may have removed and recreated the file.
Every lease and every lock attempt uses its own `open()` of the lock file; descriptors
are never shared or duplicated between lock holders, including two holders in one
process. `flock` state belongs to the open file description, so a request through a
duplicate converts the existing lock instead of contending with it: in one measured
process, an exclusive non-blocking request on a separate `open()` was refused while a
shared lease was held, the same request on a `dup()` of the lease descriptor was
granted, and another process could no longer take a shared lock
([lock descriptors](../../../../explorations/repository-cache/README.md#platform-primitives)).

Two kinds of side lock sit outside the order:

- **Liveness locks** for one staging entry, trash entry, or fetch job are held by their
  one owner, including across network work, and every other process only tries them
  without blocking. The sweep removes an entry only after acquiring its lock.
- **The store lease** is `cache/locks/stores/<store-key>.maintenance.lock`. A live
  subject, an acquisition from before its store is published until its alias is
  published, and a fetch job from before its network work until publication hold it
  shared; it may block only while its holder holds no ordered lock.
  `gc` and `repack` run under its exclusive form alone, never under the store lock, and
  reclamation, purge, and quarantine take the exclusive form before their ordered locks.
  The exclusive form never blocks, so a lease defers maintenance and refuses purge
  instead of waiting.

Every object enters a store under its lease, and every alias that names a store is
written under that store’s lease, so an exclusive holder sees a stable set of objects
and referring aliases.
`tests/fixtures/repository-cache/state-machines.json` freezes this order, the side
locks, and the acquisition, reclamation, sweep, fetch, lease, maintenance, purge,
quarantine, and repointing state machines.
Purge and quarantine move the alias before the store, under the alias and store locks.
A crash between the two moves leaves a store with no alias, which is an ordinary
unreferenced store that reclamation handles; the reverse order could leave a visible
alias naming a store that is gone.
`tests/test_repository_cache_contract_fixtures.py` checks every sequence and transition
against the order and explores every interleaving of two acquisitions, a reclamation,
and a purge from an empty cache, and of an acquisition, a reclamation, a purge, and a
quarantine from an existing alias and store with a crash allowed between each purge and
quarantine move.
No alias ever names an absent store, including after a crash; no process
violates the order or deadlocks; each crash leaves the recovery its machine declares;
and the defensive `store_missing` transition is unreachable.
The same exploration finds the race in each design it replaced: an acquisition that
released its store lock before publishing the alias without holding a lease, from both
starting states, and purge or quarantine moving the store first.

A store no alias was seen to name is quarantined under its exclusive maintenance lock
and store lock alone, with no source-alias lock.
An alias names a store only when written under that store’s lease, which the exclusive
lock excludes, so none can appear during the quarantine; one published before the lock
was taken is caught by verifying under the store lock that no alias names the store,
which falls back to the alias-first moves.
The exploration covers that variant from an unreferenced store with a concurrent
acquisition and reclamation and a crash before each of its lock steps, and finds no
stranded alias. It shows both defenses matter: a variant that skips the check under the
store lock strands an alias, while an acquisition without the lease that still
re-verifies the store under the store lock reaches `store_missing` instead of publishing
an alias to the quarantined store.
The checker gives each process its own locks, which is sound only because of the
per-`open()` rule above.
The implementation’s concurrent refresh/read/purge/reclaim tests replay those machines.

## Application Home and Cache Layout `f01`

The first released logical layout is:

```text
~/.metabrowser/
├── config.yml
└── cache/
    ├── CACHEDIR.TAG
    ├── layout.yml
    ├── locks/
    │   ├── home.lock
    │   ├── sources/<slug>.lock
    │   ├── stores/<store-key>.lock
    │   ├── stores/<store-key>.maintenance.lock
    │   ├── staging/<entry>.lock
    │   ├── trash/<entry>.lock
    │   └── jobs/<job-id>.lock
    ├── staging/
    │   └── <entry>/
    ├── trash/
    │   └── <entry>/
    ├── quarantine/
    │   └── <entry>/
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

Phase 0 fixed the generic spellings: directories are flat, with no sharding, because a
scan of 10,000 flat source entries that also reads each `source.yml` took 262 ms and
1,000 took 21 ms on the measured home; `<store-key>` is all 64 hexadecimal digits of the
store identity; and `<uniquified-slug>` follows
`tests/fixtures/repository-cache/source-identity.json`. Lock files exist before the
directories they guard are published, so a read-only cache hit opens them without
creating state. The ownership is fixed as well: source aliases, shared Git stores, and
stable provider repositories are siblings.
Provider observations never live under a source entry, and the Git store contains no
checkout. A source holds exactly one provider binding, so each source key names one
binding file. Later schemas may change a physical spelling before release; they may not
collapse those owners.

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
  written_by: 0.11.0
  upgrades:
    - version: 0.12.0
      at: "2026-12-01T00:00:00Z"
```

The versions are illustrative; the implementation writes its actual release.
Config is `permissive` because a compatible older client must preserve unknown user
settings, at every level.
Known fields still validate.
Credentials are forbidden: a key naming a token, password, secret, credential, or API or
private key is refused anywhere in the file.
The config models no cache root, because `METABROWSER_HOME` is the only override, and no
refresh policy, because v0.11 refresh is explicit; a `cache` mapping a user writes is
kept as an unknown setting and not honored.
Metabrowser writes `config.yml` only when it creates or migrates the home, keeping every
setting but not comments, and refuses a config it cannot read rather than replacing it.

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
| `staging/` | An in-progress clone must be invisible until it is complete | Startup sweep: list entry names under the application-home lock, release it, then delete each entry whose liveness lock is free |
| `trash/` | Purge should be recoverable for a moment, not forever | Purge deletes it at the end of its own run; the same sweep removes anything a crashed purge left |
| `quarantine/` | The entry may be the only local copy of an unavailable source | Never automatically. Explicit inspect and purge only |

The sweep decides liveness by trying the entry’s lock, not by age.
No age threshold can tell a slow clone from a dead one, while a crashed holder’s `flock`
released within 2.8 ms in the measurements.
Deletion runs outside the home lock because removing a large store can take long enough
to stall a migration or catalog scan.

`staging/` is the one that actually leaks: an interrupted clone leaves a tree behind,
and the publication guarantee is only that no *visible incomplete entry* results, which
is a weaker property than “nothing is left on disk”.
Git removes its own destination after SIGTERM, but a SIGKILLed clone left the
destination and a temporary pack in every measured run.
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
github-com--pallets--flask--e7b7fe0ffe8a
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

Phase 0 froze the exact rules as data.
`tests/fixtures/repository-cache/url-grammar.json` classifies every root argument as a
Git source, a local path, or a typed rejection reason, in a fixed check order, with the
normalized address for every accepted source.
`tests/fixtures/repository-cache/source-identity.json` derives the source identity from
that normalized address and its transport, derives the generic and provider store
identities, and derives slugs, with collision extension and equivalence classes.
The slug is lowercase ASCII because the measured application-home filesystem folds both
case and Unicode normalization, so any other spelling could alias a different directory.
A slug is recorded at creation and never recomputed, so its readable length can change
later without orphaning entries.

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
  configuration_digest: sha256:<configuration-snapshot-digest>
  default_remote_ref: refs/remotes/origin/main
  default_revision: <full-object-id>
  object_state: converging
  last_fetch_at: null
  last_operation:
    kind: acquire
    outcome: succeeded
    at: "<RFC-3339 timestamp>"
```

`configuration_digest` is the store’s configuration snapshot.
It lives in `state.yml` rather than `store.yml` because it is mutable: it is recorded
after the first successful fetch and before publication, and only an operation that
intentionally changes the store’s configuration replaces it, under the store lock.

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
to Git helpers such as `ext::` are rejected before Git sees them; the complete grammar
and its reasons are `tests/fixtures/repository-cache/url-grammar.json`. Production clone
policy sets `protocol.allow=never` and explicitly enables HTTPS, SSH, and `file`.

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
  -> derive identity
  -> take a staging liveness lock, then create same-filesystem staging
  -> observe the remote HEAD with ls-remote --symref
  -> fetch a worktree-free Git database with the blob filter
  -> record whether the remote honored the filter
  -> if it did, fetch the pinned revision's blob-mode entries by object ID
  -> validate objects, refs, and records
  -> take the store lease
  -> publish the store with no replacement
  -> create the source alias as the final visibility commit, then release the lease
  -> serve an immutable revision subject immediately
  -> converge the remaining objects in background by explicit object-ID fetches
```

The `store_acquisition` machine in `tests/fixtures/repository-cache/state-machines.json`
names each step’s locks, network work, visibility, and crash recovery.
A remote that ignores the filter produces a store with every reachable object, recorded
as strategy full and object state complete, never as partial.
A prefetch that fails in transport or hits its stall bound still publishes, with object
state partial and the default revision’s missing content deferred; cancellation abandons
the staging entry instead.

Publication’s guarantee is verify-absent-under-lock plus rename: under the owning
ordered lock the target path is checked absent with `lstat`, and the staged directory or
record is renamed into place.
That is sufficient because every Metabrowser writer of the path takes the same lock.
Where the platform offers an atomic no-replace rename it is used for the same rename as
defense in depth — `renameat2` with `RENAME_NOREPLACE` on Linux and `renamex_np` with
`RENAME_EXCL` on macOS, through `ctypes` with no new dependency — so a violated lock
discipline fails instead of silently replacing an entry.
On the measured filesystem `os.rename` replaced an existing empty directory, while
`renamex_np(RENAME_EXCL)` refused it; `renameat2` was not measured.

All Git work continues through `metabrowser.git.process`, which now exposes two seams:
`run_git` for bounded buffered commands, and `spawn_git_process` plus
`terminate_git_process` for a caller-owned streaming process.
Acquisition is a buffered command, so it uses `run_git`, which gains request,
acquisition, and background policies rather than a parallel subprocess wrapper.

Background convergence is the one piece that may want the streaming seam, and if it
takes it, the lifecycle rules that continuous history established apply in full: bound
the count, bound the storage, expire on idle, release on shutdown, and drain output
before reaping. See
[Git and comparison sources](../../architecture/arch-git-and-comparison-sources.md#long-lived-walks).
Every policy retains fixed arguments, no shell, bounded output, cancellation cleanup,
and scrubbed repository-pinning environment variables.
Acquisition also sets `stdin=DEVNULL`, disables terminal and credential-manager prompts,
uses SSH batch mode, creates stores with an empty Git template, and disables submodule
recursion, hooks, bundle URIs, automatic maintenance, unsafe transports, and unsafe
symbolic-link traversal.
Every Git child runs with umask `077`. Automatic maintenance is disabled in the store
configuration itself (`maintenance.auto=false`, `gc.auto=0`), not only on the command
line, because every fetch — including each implicit lazy fetch — otherwise spawns a
detached `git maintenance run --auto`, and over HTTPS that maintenance made the 51st
consecutive lazy fetch fail with
`… in the commit graph file but not in the object database`.

Objects enter a store only from the promisor remotes recorded in its configuration
snapshot, which Metabrowser writes when it creates the store.
A fetch job names one of those remotes, never a URL. Fetching a fork by URL into a
blobless store with the filter wrote `remote.<url>.promisor` and
`remote.<url>.partialclonefilter` into the store’s configuration, and without the filter
it wrote objects that made `gc --prune=now` fail.
Provider change-request heads are therefore fetched from the base repository’s
provider-published refs — `refs/pull/<n>/head` on GitHub, `refs/merge-requests/<n>/head`
on GitLab — through the store’s own remote; fetching the same commit that way left the
configuration unchanged and `gc` and `repack` succeeded.
An object reachable only from a fork is acquired through the fork’s own source and
store, never fetched by URL into another store.

**Configuration snapshot.** After the store’s first successful fetch in staging and
before publication, acquisition records a digest of the store’s configuration in the
repository-store state record: SHA-256 of the exact output bytes of
`git config --file <store>/repository.git/config --list -z`, run with no system or
global configuration.
`--file` reads only that file and does not follow `include.path`, so an include is
itself a recorded key, and entries stay in file order.
Any Metabrowser operation that intentionally changes the configuration updates the
digest under the repository-store lock in the same step.
Every Git process spawned on a store verifies the digest first, credentialed or not:
each batch-reader spawn (a running reader is not re-checked per request), each other
read, each fetch job and its publication, and each maintenance run.
A planted `core.sshCommand`, `remote.<name>.uploadpack`, `diff.external`,
`include.path`, `url.<base>.insteadOf`, or credential helper therefore changes the
digest before Git can use it.
On a mismatch Git is not run: the process marks the store suspect and refuses reads and
fetches on it, releases any lease, and requests quarantine, which takes the exclusive
maintenance lock without blocking and is deferred while a lease is held; the store stays
refused meanwhile.
An exact expected configuration cannot be written in advance: Git adds
`remote.origin.promisor` and `remote.origin.partialclonefilter` on the first filtered
fetch, and on macOS `init` writes `core.ignorecase` and `core.precomposeunicode`. After
the first fetch, a job fetch into private refs, an object-ID prefetch, an `update-ref`
transaction, `gc --prune=now`, `repack -a -d`, and a store read left the digest
unchanged
([store configuration](../../../../explorations/repository-cache/README.md#store-configuration-fork-sources-and-retention)).

The hooks path is `core.hooksPath=/dev/null`. With the key unset, a
`reference-transaction` hook planted in the store’s `hooks/` directory ran on
`update-ref`; with `/dev/null` it did not, and neither setting ran a hook placed in the
process’s working directory.

Initial acquisition has no low-speed bound yet: the one measured stall bound was
measured on object-ID fetches, and a large or bitmap-less acquisition may legitimately
send nothing for longer while the server counts and compresses objects.
Until Phase 1B-a measures that case, user-driven job cancellation is the guard against a
stalled clone.

A cache hit validates the source and store and serves a full-OID subject without fetch,
credential lookup, or background refresh.
This rule is observable and tested.
A failed convergence leaves the published store usable and honestly marked partial; it
does not turn a successful open into a fatal error.

### Blobless acquisition and the offline guarantee

These two commitments are in tension, and the plan previously held both without
reconciling them:

- a cache hit is an offline operation, served without fetch; and
- initial acquisition is blobless, with the missing objects arriving afterwards.

A blobless clone does not contain file content.
Git fills that in lazily from the promisor remote at the moment something reads a
missing blob — so between publication and convergence, a read on a *server request path*
can attempt network I/O. The project’s own research observed exactly this failure rather
than reasoning about it: a blame in a blobless clone failed outright with
`could not fetch … from promisor remote` while the network was intercepted.

That makes “offline cache hit” true for history and tree structure and false for file
content, which is not a distinction a user should discover by having a request hang.

Phase 0 considered three options, in preference order:

1. **Disable lazy fetch on read paths** (`--no-lazy-fetch` / `GIT_NO_LAZY_FETCH`) and
   map a missing object to the existing `deferred` or `unavailable` availability, which
   convergence flips to `ready`. Reads stay bounded and offline by construction, and the
   honest partial state the plan already models carries the meaning.
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

**Decided 2026-09-16: option 1, with option 2 as its gate.** Every Git read on a request
path runs with `GIT_NO_LAZY_FETCH=1`, and acquisition is gated on Git releases that
honor it; the security floor below already guarantees that, so there is no separate
blobless gate. Measured on Git 2.50.1 against a blobless flask store with GitHub as its
promisor
([lazy fetch](../../../../explorations/repository-cache/README.md#lazy-fetch-against-real-and-failing-remotes)):

- with lazy fetch allowed, a remote that accepted the connection and never answered held
  a single blob read past the 20 s harness timeout, and `ls-tree -r -l` issued one
  request per blob, 230 requests in 135 s;
- `remote.origin.promisor=false` did not stop the fetch, because
  `extensions.partialClone` still names the promisor, so only the environment variable
  or `--no-lazy-fetch` is a control, and only the environment variable exists across the
  admitted releases;
- with lazy fetch disabled the same read failed in 8 ms, and `cat-file --batch-command`
  answered `<oid> missing` and stayed framed for the next request.

Option 3 is rejected rather than merely deferred: the one thing it buys — a blobless
entry that stays readable online — is delivered instead by explicit object fetches from
the object-job port, which can be bounded, cancelled, coalesced, and reported.
A missing object becomes `object_unavailable` or `deferred`, and convergence flips it to
`ready`. The diff routes check before they run: they list the change set with
`git diff --raw -z --no-abbrev --no-renames`, check it with `cat-file --batch-check`,
and report `deferred` while requesting exactly the missing blobs.
In 40 of 40 measured comparisons, including 50-commit ranges, that set was sufficient
for commit detail, the comparison manifest, and patches to succeed with lazy fetch
disabled. `--no-renames` is required, because porcelain `git diff` enables rename
detection by default and inexact rename detection reads blobs.
Checking first also avoids the failure path itself, which took 93–488 ms per invocation
against 10–15 ms for success.

Only blob-mode entries (`100644`, `100755`, `120000`) are requested.
A `160000` gitlink names a commit in another repository: `cat-file --batch-check`
reports it missing, and a want list containing one failed with `not our ref` under
protocol v0 and v2 and fetched nothing
([gitlinks](../../../../explorations/repository-cache/README.md#gitlinks-and-rejected-object-requests)).
Gitlinks are reported as submodule entries, never requested, and never missing.
When the server rejects a request object by object (`not our ref`), the job splits the
want list in halves down to single object IDs, fetches the accepted ones, and marks each
rejected ID unavailable; the measured list of 13 with a gitlink and an absent object
took 13 requests and fetched all 11 blobs.
A job stops splitting after 8 rejected IDs and marks every ID it has not resolved
`deferred`, not unavailable, so convergence retries them.
That cap is a provisional cost policy, not a performance bound: nothing measured how
often hosting providers reject objects, blob-mode filtering removes the one routine
cause that was measured, and 8 keeps a job at 50,000 IDs to at most 1 + 2 × 8 × 16 = 257
requests. A policy refusal, transport failure, stall, cancellation, or any failure text
that matches no known class fails the whole job without splitting.
`tests/fixtures/repository-cache/object-requests.json` pins these rules and the
fetch-job source rule.

Store reads also disable the mailmap with `-c mailmap.blob= -c mailmap.file=`. A bare
store’s default mailmap is `HEAD:.mailmap`, so with Git defaults the history page and
`show --raw` each read that blob, and with lazy fetch disabled they printed
`error: unable to read mailmap object at HEAD:.mailmap` and still exited 0.
`log.mailmap=false` alone did not stop a `%aN` placeholder from reading it, and
`mailmap.blob=` alone still applied an inherited `mailmap.file`; the two keys together
stopped every read and kept raw identities in every measured command
([mailmap](../../../../explorations/repository-cache/README.md#store-reads-and-file-modes)).
The current route formats use `%an` and `%ae`, so their output does not change.
Because Git can report a failed read on stderr and exit 0, a store read that writes to
stderr is not silently treated as success: the process boundary logs it and the route
reports the result as degraded or unavailable.

“Read of a not-yet-converged blob, online and offline” joins the Phase 1B acceptance
list beside interrupted clone and unavailable network, and its outcome is the same in
both: a typed `object_unavailable` or `deferred` result in bounded time, never a request
that waits on the network.

### Git version gates

Phase 1B detects the Git version once and gates separate things on it.
They are listed separately because they have different floors and different
consequences, and a single unnumbered “supported Git” would hide that.
`tests/fixtures/repository-cache/git-version-gates.json` is the machine-checked form,
with the parsing rule and version-string cases.

| Gate | Floor | Below the floor |
| --- | --- | --- |
| Acquisition, including blobless acquisition | **Patched release:** 2.43.7, 2.44.4, 2.45.4, 2.46.4, 2.47.3, 2.48.2, 2.49.1, 2.50.1, or any newer release | URL opening is refused with a typed `unsupported_git_version` state naming the detected and required upstream versions. Local-path browsing is unaffected |
| Cache integrity (`is_clean`) | **2.36** | Reported unavailable, never inferred clean — see the [Git-status plan](plan-2026-08-26-git-status-and-working-tree-diffs.md) |

The acquisition floor is a security floor, decided 2026-09-16 from upstream release
notes.
CVE-2025-48384, submodule path handling that can execute a hook through a symlink,
and CVE-2025-48385, bundle-URI protocol injection during clone, were fixed together in
the maintenance releases listed above; 2.43 is the oldest track that received them, and
the same releases carry the 2024 clone fixes (CVE-2024-32002, -32004, -32020, -32021,
-32465). No later security release existed when upstream tags were reviewed, which then
ended at v2.55.0; this row is revisited at every upstream security release.
Above this floor protocol v2 is the default (it was re-enabled in 2.29 after 2.27
demoted it) and `cat-file --batch-command` (2.36) is available, so the former 2.26
capability floor no longer needs its own row.

The security floor is also the lazy-fetch floor.
In the Git source, `promisor-remote.c` `fetch_objects` returns before fetching when
`GIT_NO_LAZY_FETCH` is set, and both object reads and `diffcore-rename`’s blob prefetch
reach promisor remotes through it.
That check is present at v2.39.4, v2.43.7, v2.44.1, v2.45.1, and v2.50.1 and absent at
v2.44.0 and v2.45.0, so every admitted release has it.
The `--no-lazy-fetch` option only exists from 2.45.0 and is not used.
Phase 1B-a runs the no-lazy-fetch acceptance tests against the lowest admitted Git in CI
rather than trusting this reading.
`git backfill` is not a gate and is not used: it is experimental, covers only history
reachable from `HEAD` through 2.54 (2.55 adds a revision argument), and exited 0 without
fetching anything when `HEAD` was unborn.
The same fallback to a full fetch applies when a remote does not honor the filter, which
is detected from the objects actually received rather than from stderr: a `file://`
origin without `uploadpack.allowFilter` delivered all 118,501 objects while the store
still recorded itself as a promisor.

Version detection degrades rather than guesses: an unparseable `git version` string is
treated as below every floor, so URL opening is refused with the typed state, and the
detected string is recorded in `store.yml` under `acquisition.git_version` so a later
entry can be explained.

**Open decision, owned by `mb-h51g`: distribution backports.** Distributions backport
these CVE fixes without changing the upstream version string — for example, Ubuntu
24.04’s patched Git reports 2.43.0 and Debian 12’s reports 2.39.x — so a gate on
upstream versions refuses builds that are in fact patched.
The options:

1. **Refuse with an actionable message** naming the detected version and the upstream
   floor. Simple and never wrong about safety, but it blocks URL opening on common
   supported distributions until the user installs a newer Git.
2. **A user-set acknowledgement setting** that accepts a named detected version as
   patched. It unblocks those users with no platform code, but moves a security judgment
   to the user and can outlive the Git it described.
3. **A distribution-package check** that reads the package manager’s version and
   changelog for the fixed CVEs.
   It is accurate where it works, but it is per-platform code that is hard to test,
   fails for Git not installed from a package, and runs package tools at startup.

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

Refresh fetches Git refs, retries object convergence, and reports its stage results.
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
| `src/metabrowser/home.py` (Phase 1A) | `application_home`, `ensure_home`, `F01_DIRECTORIES`, `write_private_file_atomic`, `rename_without_replacing`, `validate_private_home`, `ensure_private_directory`, `open_private_file`, `PrivateStorageError`, `ApplicationHomeError` | Resolve `METABROWSER_HOME` without touching the file system, create the owner-only `f01` skeleton and `CACHEDIR.TAG`, publish files by exclusive temporary file and rename, rename without replacing, and reject symlinked, foreign, or permissive ancestors |
| `src/metabrowser/cache/records.py` (Phase 1A) | `ApplicationConfig`, `CacheLayout`, `RepositorySource`, `RepositorySourceState`, `RepositoryStoreAlias`, `RepositoryStore`, `RepositoryStoreState` | Strict Pydantic models; config alone keeps unknown settings |
| `src/metabrowser/cache/contracts.py` (Phase 1A) | `CACHE_CONTRACTS`, `compile_contracts`, `check_packaged_schemas`, `cache_contract_registry`, `repository_cache_capabilities`, `parse_application_config` | SoftSchema bindings to packaged schemas; the enforced contracts install through the `repository-cache` capability provider, and cache reads validate against a registry built without discovery |
| `src/metabrowser/cache/layout.py` (Phase 1A) | `LAYOUT_FORMAT`, `FORMAT_HISTORY`, `MIGRATIONS`, `read_layout`, `read_config`, `migrate_layout`, `open_cache`, `FutureLayoutFormatError`, `LayoutError` | Fail closed on future formats before writing, run ordered migrations under the home lock, publish `config.yml` last, and prepare a home for cache use |
| `src/metabrowser/cache/atomic.py` (Phase 1A) | `read_record`, `write_record_atomic`, `publish_entry`, `RecordError` | Bounded record reads, record writes by atomic rename, and publication that verifies the target absent under its owning lock |
| `src/metabrowser/cache/locks.py` (Phase 1A) | `application_home_lock`, `source_alias_lock`, `repository_store_lock`, `provider_resource_lock`, `store_lease`, `store_maintenance_lock`, `staging_entry_lock`, `trash_entry_lock`, `job_entry_lock`, `LockOrder`, `require_no_hierarchy_locks` | The fixed home → alias → ordered stores → resource order per thread, side locks, one descriptor per acquisition, identity recheck, and replacement of a shared lock file only under its old lock |
| `src/metabrowser/cache/probe.py` (Phase 1A) | `probe_application_home`, `ProbeReport` | Verify cross-process exclusion, lease semantics, survival of an unrelated close, and no-replace publication once per process per home |
| `src/metabrowser/cache/paths.py` (Phase 1A) | `LAYOUT_RECORD`, `CONFIG_RECORD`, `source_record`, `store_record`, `quarantine_entry` | Logical `f01` locations for cache modules and the read routes |
| `src/metabrowser/cache/identity.py` | Phase 1A: `source_identity`, `repository_store_id`, `provider_repository_store_id`, `store_key`, `cache_slug`, `slug_matches_identity`; Phase 1B-a: `normalize_git_source` | Credential-free source identity from a normalized address, stable internal store identity, deterministic provider-identity store derivation, and collision-extending slugs; Phase 1B-a adds the normalization that produces the address |
| `src/metabrowser/cache/urls.py` | `classify_root_argument`, `ProviderUrlReducer`, `ReducerOutcome`, `RepositorySelection` | Distinguish local paths, Git sources, and registered provider web URLs before constructing a `Path`; arbitrate declared reducer claims and terminal rejection; keep provider-specific syntax behind reducers |
| `src/metabrowser/cache/acquire.py` | `acquire_file_source`, `acquire_into_staging`, `publish_from_staging` | Acquire and publish a validated worktree-free store, then create the source alias as the final atomic visibility commit. A published `file://` hit is reused without `open_cache`. `last_opened_at` is best-effort and must not fail the hit |
| `src/metabrowser/cache/selection.py` | `resolve_selection`, `resolve_ref_path_candidates` | Resolve slash-containing branch/tag/path candidates against local and remote-tracking refs and return either a full object ID or a typed request for one explicit missing ref; performs no network work |
| `src/metabrowser/content_source.py` | `SourceSession`, `SourceCapabilities`, `ContentSource`, `ContentHandle`, `ContentEntry`, `list_directory`, `read_window`, `close` | Define one generation-owned source session for attached filesystems and immutable revisions without fabricating filesystem facts |
| `src/metabrowser/git/tree_source.py` | `GitPath`, `GitTreeSource`, `resolve_tree`, `list_tree`, `read_blob`, batch-reader actor lifecycle | Enumerate NUL-framed byte-safe full-OID trees and read size-gated blobs directly from the shared store |
| `src/metabrowser/provider_resources/models.py` | `AuthorizationContextRef`, `authorization_context_key`, `LocalObjectAvailability`, `LocalGitObjectAvailability` | Move the non-secret context record, its one canonical key function, and the local object-availability vocabulary and report out of the hosted-review plugin before core consumes them; the observation-guarded constructors stay in `hosted_review/models.py`, and `mb-s0gv` later moves the remaining neutral provider records |
| `src/metabrowser/plugin_api.py` | opaque `GitFetchCredentialLease`; `RepositoryObjectJobPort.request_selected_refs`, `provider_fetch_authorization_context` | Define the public opaque registry handle; validate an `AuthorizationContextRef`, derive its canonical key, and map the record once to an internal `ProviderPrincipal`; and let trusted provider plugins pass the handle without importing Git internals |
| `src/metabrowser/git/process.py` | `GitCommandTarget`, `run_git`, `spawn_git_process`, askpass bridge | Keep one Git subprocess boundary; in Phase 3A, project a validated broker credential under the environment, configuration, and prompt-binding isolation of the repository-source architecture without exposing its secret |
| `src/metabrowser/cache/repository_store.py` | `FetchAuthorizationContext`, `resolve_store`, `stage_fetch`, `publish_refs`, `lease_revision`, `converge_store`, `reclaim_objects` | Derive deterministic provider store IDs, isolate fetches by source and closed non-secret auth context in job-private refs, compare-and-swap public refs and aliases, and protect leased and durable revisions |
| `src/metabrowser/cache/service.py` | `RepositoryOpenTarget`, `resolve_open_target`, `close_open_target` | Orchestrate parse, acquire/reuse, selection, immutable subject creation, trust profile, and initial browser path for CLI and later chooser callers |
| `src/metabrowser/cache/jobs.py` | `RepositoryJob`, `RepositoryJobRegistry`, `fetch_selected_ref`, `request_ref_fetch`, `GitFetchCredentialLeaseRegistry`, `validate_git_fetch_credential_lease`, `close_all` | Own bounded network fetch/prune for explicit selected refs plus provider-neutral progress, cancellation, the lease registry, per-request context/lease/source validation before job lookup, and stage outcomes used later by provider plugins |
| `src/metabrowser/cache/routes.py` | Phase 1A: `CACHE_ROUTES`, `api_cache_layout`, `api_cache_sources`, `api_cache_source`, `api_cache_stores`; later: `api_repository_jobs` | Read-only logical-state projections for CLI parity; acquisition remains a CLI action, not a write API |
| `src/metabrowser/cache/projection.py`, `wire.py`, `listing.py` (Phase 1A) | `layout_response`, `sources_response`, `source_response`, `stores_response`, `page_limit`; the `Cache*Response` shapes; `list_private_directory` | Resolve the home per request without creating it, read records and verified listings without locks, bound pages and reference scans, and project records into path-free wire shapes |
| `src/metabrowser/cache/reclaim.py` | Phase 1A: `reclaim_staging`, `reclaim_trash`, `sweep_staging_and_trash`, `begin_trash_entry`, `move_to_trash`, `quarantine_entries`, `purge_quarantined`, `reclaim_store`, `reclaim_unreferenced_stores`; later: `reclaim_repository_objects` | Briefly enumerate under the home lock, then recover interrupted staging and trash, quarantine and purge entries, and reclaim unreferenced stores; later reclaim unreachable objects under store locks while honoring revision and provider leases |

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
| Formats, permissions, migration, identity, publication | `tests/test_cache_records.py`, `tests/test_cache_layout.py`, `tests/test_cache_permissions.py`, `tests/test_cache_atomic.py`, `tests/test_cache_locks.py`, `tests/test_cache_reclaim.py`, `tests/test_repository_cache_contract_fixtures.py`, `tests/test_cache_acquire.py` |
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

- [x] Remeasure full, blobless, and blobless-plus-backfill acquisition against the
  v0.10.0 history session, commit detail, comparison manifest, deferred patches,
  revision content, and canonical path-identity routes.
- [x] Review upstream through v0.8.0 and remove assumptions superseded by shipped Git
  history, revision, and diff infrastructure.
- [x] Review SoftSchema v0.7.0 and its enforced-composition boundary; install its Codex
  skill for future implementation turns.
- [x] Separate generic cache delivery, cache operations, chooser, GitHub modeling,
  GitHub acquisition, provider views, stack projections, and large-repository work.
- [x] Freeze the safe URL grammar, source identity, slug, lock, staging, publication,
  quarantine, and trash state machines as fixtures.
- [x] Measure concurrent subjects, fetch coalescing, cancellation, multi-process
  contention, maintenance, and object retention, and record the decisions below.

#### Phase 0 decisions

Decided 2026-09-16. The measurements, method, environment, and raw results are in
[Repository cache measurements](../../../../explorations/repository-cache/README.md).
They were taken on one macOS machine with Git 2.50.1 against `pallets/flask` and
`python/mypy` over HTTPS and from `file://` origins, so the numbers below explain a
decision; they are not cross-machine budgets.
The machine-checkable contracts are in `tests/fixtures/repository-cache/` and pinned by
`tests/test_repository_cache_contract_fixtures.py`, which the implementation’s own tests
replay against production functions when they land.

| Decision | Frozen as | Measured basis |
| --- | --- | --- |
| Store layout | A bare repository created with `git init --bare --template=`, configuration written only by Metabrowser, and one fetch with explicit refspecs into Metabrowser-owned refs; `HEAD` is set from the observed remote `HEAD` | Cost did not distinguish layouts: bare and `--no-checkout` full clones overlapped (flask 2.83 s against 3.25 s, mypy 11.64 s against 15.54 s, disk within 1%). State did: `--no-checkout` leaves `core.bare=false`, an empty work tree, reflogs, and a local branch; `clone --bare` writes remote branches into `refs/heads/`. The explicit form costs one `ls-remote --symref` round trip (4.21 s and 13.94 s full) |
| Acquisition strategy | Blobless when the version gate passes; before publication, fetch the pinned default revision’s blob-mode entries in one object-ID request; after publication, converge the rest in the background. Full fetch below the gate or when the remote ignores the filter, recorded as complete. No size threshold | The decision rests on mypy and on coverage, not on flask. Over HTTPS, back to back, the default revision’s content was complete in 5.8–5.9 s blobless against 8.8–17.8 s full for mypy; flask’s advantage was small and variable (1.1× and 1.4× across two pairs). Every object took longer blobless (21.3–29.7 s against 8.8–17.8 s for mypy), which is why convergence runs after serving. Generic Git advertises no repository size before transfer, so a threshold would need a provider API the generic cache may not use |
| Convergence | Explicit `git fetch --stdin` of the missing object IDs listed by `rev-list --objects --missing=print`, at most 50,000 IDs per request; `git backfill` is not used | Coverage decides it: backfill left 1,318 mypy objects outside `HEAD`’s history missing, and did nothing when `HEAD` was unborn. Speed does not: one request of 53,607 IDs took 16.2 s and 24.9 s against 25.5–26.0 s for backfill plus its remainder, but only two runs were taken, always after backfill, so order effects are not excluded. No larger request was measured |
| Object-fetch stall bound | Object-ID prefetch and convergence fetches set `http.lowSpeedLimit=1000` and `http.lowSpeedTime=30`. Initial acquisition has no low-speed bound until Phase 1B-a measures one; user cancellation is the interim guard | Git defaults waited past 20 s on a remote that never answered; a 1 B/s over 3 s bound failed in 3.13 s; the 30 s bound interrupted none of the eight measured object-ID fetches, the longest 24.9 s. No stall bound was measured on an acquisition, where a server may send nothing while it counts and compresses objects |
| Lazy fetch | `GIT_NO_LAZY_FETCH=1` on every request-path read; diff routes check the `--no-renames` change set first; network only through the object-job port | See [the offline guarantee](#blobless-acquisition-and-the-offline-guarantee) |
| Object requests | Only blob modes `100644`, `100755`, and `120000` are requested; gitlinks are submodule entries; a per-object rejection splits the request in halves down to single IDs, at most 8 rejected IDs per job, after which unresolved IDs are deferred; unclassified and other failures fail the job; `object-requests.json` | A want list with a gitlink failed with `not our ref` under protocol v0 and v2 and fetched nothing; splitting a 13-ID list with a gitlink and an absent object took 13 requests and fetched all 11 blobs. The cap of 8 is a provisional cost policy, bounding a job to 257 requests, not a measurement |
| Store reads | Every store read runs with `GIT_NO_LAZY_FETCH=1`, `-c mailmap.blob=`, and `-c mailmap.file=`; stderr from a read is logged and degrades the result instead of passing as success | With Git defaults the history page and `show --raw` read `HEAD:.mailmap` and, with lazy fetch disabled, printed an error and exited 0. `log.mailmap=false` alone did not stop a `%aN` read, and `mailmap.blob=` alone still applied an inherited `mailmap.file`; the two keys stopped every read |
| Store configuration | `maintenance.auto=false`, `gc.auto=0`, `fetch.recurseSubmodules=false`, `transfer.bundleURI=false`, `core.hooksPath=/dev/null`, empty template, no user configuration, umask `077` for every Git child, and a configuration snapshot digest that every Git process verifies first; Git-written content must have no group or other bits and no allow ACL for another principal, and `0400` object files are accepted | Every fetch with Git defaults spawned `git maintenance run --auto`; over HTTPS the resulting auto-gc made the 51st lazy fetch fail with a commit-graph error, while the same run with maintenance disabled completed 230 fetches. Under umask `022` Git wrote `0755` directories and `0444` or `0644` files, and `core.sharedRepository=0600` left six of seven directories `0755`; under umask `077` no entry had a group or other bit. Git adds promisor keys on the first filtered fetch and macOS `init` writes `core.ignorecase` and `core.precomposeunicode`, so the snapshot is taken after that fetch; six later store operations left it unchanged. With `core.hooksPath` unset, a hook planted in the store’s `hooks/` directory ran on `update-ref`; with `/dev/null` none ran |
| Batch readers | Per repository store per process, at most 4 `cat-file --batch-command --buffer` actors, created on demand; each serves one request at a time; cancellation terminates the process and a later request starts a new one | Whole-tree throughput peaked at 4 actors (54.8–57.2 k blobs/s against 31.3–31.7 k for one) and fell with 8 (45.0–46.4 k); `info` plus `contents` p99 stayed at or below 0.25 ms with two actors; a reader exited within 0.77 ms of a signal, and a restart answered its first request in 9.3 ms (p50) |
| Concurrent subjects | No per-subject isolation beyond pinned object IDs | Two readers on different object IDs ran concurrently in 0.063 s against 0.12 s sequentially with byte-identical output in 3 of 3; readers saw no failure or missing object across `repack -a -d` and `gc --prune=now`, and an actor started before maintenance found 200 of 200 objects afterward |
| Fetch jobs and coalescing | A network job holds the store lease and no ordered lock, verifies the configuration snapshot, fetches from a promisor remote recorded in that snapshot directly into the store, never from a URL, and writes only `refs/metabrowser/jobs/<job-id>/`; it then takes the store lock briefly and runs one `update-ref --stdin` transaction that compare-and-swaps the public refs from their observed old values and deletes its job refs. In-process coalescing on the exact job key is required; cross-process duplicates cost space until maintenance compacts them. Provider change-request heads come from the base repository’s published refs through the store’s own remote, and an object reachable only from a fork is acquired through the fork’s own source and store; `repack.writeBitmaps` is left at Git’s default | On a blobless flask store, four concurrent direct jobs never failed (2 of 2 repetitions); one published and three found the same object IDs already published, leaving no job refs. They received 4.0× the bytes of one coalesced job (34,356 against 8,520 and 70,002 against 17,480) and added three extra packs, all promisor packs; `gc --prune=now` and `repack -a -d` then succeeded in 4 of 4 runs, compacted to one promisor pack, wrote no bitmap, and lost no object. The replaced alternate-staging design failed on the same blobless store: a filtered staging import failed with `possible repository corruption on the remote side` (2 of 2), and an unfiltered import succeeded but made `gc --prune=now` and `repack -a -d` fail with `Packfile doesn't have full closure` while writing bitmaps (2 of 2), because the imported pack was not a promisor pack. Fetching a fork by URL into a blobless store wrote `remote.<url>.promisor` into its configuration with the filter and made `gc --prune=now` fail without it, while the base repository’s `refs/pull/1/head` through `origin` did neither |
| Retention | Every object promised for offline reuse is reachable from a durable Metabrowser-owned ref; maintenance requires the exclusive maintenance lock. In a blobless store, objects fetched by a discarded or crashed job stay after their job refs are deleted, until an explicit compaction that later cache operations own | In a full store a commit behind a private ref survived `gc --prune=now`, and without a ref it survived only the default two-week prune window; bare stores write no reflogs. In a tiny blobless store a discarded job’s commit and blob both survived `gc --prune=now`, `repack -a -d`, and `prune --expire=now`, because Git never prunes promisor objects; the same objects in a full store were removed by the first of those |
| Version floors | One acquisition floor, which is both the security floor and the lazy-fetch floor; [Git version gates](#git-version-gates) and `git-version-gates.json` | Upstream release notes, and `promisor-remote.c` and `diffcore-rename.c` read at each relevant tag; only 2.50.1 was available to run |
| URL grammar | `url-grammar.json` | Git’s HTTP client sent the same request with and without a trailing slash, and sent `//`, `%72`, and path case verbatim |
| Source and store identity, aliases, slugs | `source-identity.json` | The home filesystem folded case and Unicode normalization, and `NAME_MAX` was 255 bytes |
| Locks and state machines | `state-machines.json`, with the lock order and store lease above; publication verifies absence under the owning lock, with a platform no-replace rename as defense in depth | `flock` released 2.8 ms after its holder was killed; `lockf` vanished when an unrelated descriptor closed; `os.rename` replaced an empty directory and `renamex_np(RENAME_EXCL)` refused it. The interleaving check found the store-to-alias reclamation race in the previous design and none in this one |
| Catalog layout | Flat `sources/` and `repository-stores/` directories | Scanning 10,000 flat entries and reading each record took 262 ms |

Store and alias rules follow from those identities.
A store acquired from a source before provider resolution takes a deterministic identity
from the source identity and its object format, so two concurrent acquisitions of one
source converge on one store and the loser discards its staging copy.
A provider-proven store takes the domain-separated provider identity instead.
An alias moves only by compare-and-swap under the source-alias and store locks, and
stores are never merged from owner/name text.

Evidence was insufficient to freeze the following; each names the phase that decides it:

- Tree-index and immutable directory-index bounds, and any revision-specific preview or
  raw limits, need browser measurements: Phase 1B-c.
- Cross-process retry and contention bounds for fetch publication: Phase 2B. No
  contention failure occurred to bound.
- Lock, rename, and case semantics beyond macOS APFS: CI runs only on `ubuntu-latest`,
  so Linux is covered by the test suite, and Windows and network filesystems — where
  `flock` may be emulated with record locks that behave like the rejected `lockf` — are
  covered only by the runtime probe Phase 1A (`mb-4gnu`) adds at application-home setup.
- The initial-acquisition stall bound, on a large or bitmap-less repository: Phase 1B-a
  (`mb-h51g`).
- Whether distribution builds that backport the CVE fixes under an older version string
  are admitted: Phase 1B-a (`mb-h51g`); see [Git version gates](#git-version-gates).
- SSH acquisition and prompt suppression, and Git for Windows version strings: Phase
  1B-a. Neither was measured.
- How GitHub and GitLab word a per-object want rejection, which decides what the request
  split may classify instead of failing: GitHub in the broker-pinned Git credential
  bridge (`mb-s123`), GitLab in the GitLab adapter (`mb-51uj`).
- Compaction of unreachable promisor objects left by discarded or crashed fetch jobs:
  later cache operations.
- Prune expiry, size accounting, and eviction: later cache operations.
- Convergence batches above 53,607 object IDs and repositories larger than mypy: later
  very-large-repository work.
- Git ref refresh age: later cache operations; v0.11 refresh is explicit.

### Phase 1A: Format foundation — infrastructure PR

This phase produces no user-visible result and stands between the goal and the first
repository that opens, so its scope is stated rather than assumed.

**Not negotiable**, because each one is what makes an interrupted or concurrent
operation safe rather than corrupting: source identity, publication that verifies
absence under the owning lock before it renames, application-home locking, honest
recorded state, `CACHEDIR.TAG`, the `staging`/`trash` reclamation sweep, and
compiled-schema drift checking.
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

- [x] Add the application-home resolver, `config.yml`, `cache/layout.yml`, format
  history, future-format failure, and sequential migration harness.
  Nothing in this phase was deferred: `FORMAT_HISTORY` and `MIGRATIONS` exist with `f01`
  as their only format, and the harness is tested with injected histories.
- [x] Adopt the exact released SoftSchema package after dependency and lock review;
  verify the `frontmatter-format` minimum and artifact hashes against released package
  metadata; record its `jlevy` first-party exemption and reviewed predecessor in
  *Audited First-Party Exceptions*; register the config, layout, repository-source,
  repository-store, and store-state contracts.
  Phase 0C.1 adopted and reviewed `softschema==0.8.1`; this phase changed no dependency
  and registered the config, layout, source, source-state, alias, store, and store-state
  contracts.
- [x] Package deterministic compiled schemas and add compile-drift, corpus-validation,
  schema-inventory, and installed-wheel checks.
- [x] Add atomic YAML reads/writes, application-home locking, quarantine, and
  recoverable-trash primitives without cloning or serving a URL.
- [x] Enforce owner-only application-home paths (`mb-xa0p`) and refuse remote writes
  through symlinked, foreign-owned, or permissive cache ancestors.
- [x] Freeze the lock hierarchy: home for layout/global enumeration, source alias for
  alias publication, repository stores in ascending ID order for ref/object publication
  and leases, then provider/resource for provider publication; never hold one across
  network work.
- [x] Write `CACHEDIR.TAG` when the cache root is created, and add the startup
  `staging/`/`trash/` reclamation sweep, so no released phase accumulates unreclaimed or
  backed-up cache data.
- [x] Prove config preserves unknown settings while machine records reject unknown
  fields and cache-controlled schema paths cannot redirect validation.
- [x] Probe the application home at setup (`mb-4gnu`): a second process cannot take a
  held lock, closing an unrelated descriptor for a lock file does not release the lock,
  a lock attempt through a separate `open()` in the same process contends with a held
  lease instead of converting it, and verify-absent-under-lock publication with the
  platform no-replace rename refuses an existing target.
  A home that fails any probe is refused as unverifiable, because CI covers only Linux
  and a network filesystem can emulate `flock` with record locks.
- [x] Replace the test oracle for the contracts this phase implements — store and source
  identity, slugs, the lock order, and the sweep, quarantine, and reclamation machines —
  with the production functions, and replay the same `tests/fixtures/repository-cache/`
  fixtures against them.
- [x] Add the read routes `/api/cache/layout`, `/api/cache/sources`,
  `/api/cache/source/{slug}`, and `/api/cache/stores`, projecting the records above, and
  pin them with a golden through `metab --api`.
  `tests/golden/cli-api-cache.tryscript.md` pins them against homes the production
  writers build in the sandbox.

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

#### Phase 1A implementation decisions

Where this plan left latitude, the format foundation decided the following; the module
docstrings under `src/metabrowser/cache/` and `src/metabrowser/home.py` carry the
detail.

- **Entry point.** `metabrowser.cache.layout.open_cache` resolves the home, runs
  `ensure_home`, probes, migrates, and sweeps.
  Nothing calls it yet, and ordinary local browsing never resolves, validates, creates,
  or imports the application home, which `tests/test_cache_layout.py` proves with a
  missing, permissive, and symlinked `METABROWSER_HOME`.
- **Resolution.** An empty, relative, or `..`-containing `METABROWSER_HOME` is refused
  rather than ignored, so a harness that meant to isolate the home cannot fall back to
  the real one.
- **Probe cost and caching.** One `python -I -S` child plus a staging entry; about 37 ms
  on a loaded macOS machine.
  The result is kept for the life of the process, keyed by the device and inode of
  `cache/locks`; a refused home is probed again next time.
- **Registration.** The enforced contracts install through a `repository-cache`
  capability provider, so the generic inventory gate, the architecture table check, and
  the isolated-wheel smoke test cover them; cache reads validate against a registry the
  cache builds itself, so a broken third-party plugin cannot make the cache unreadable.
  The installed registry admits only enforced contracts, so the permissive config
  contract is drift-checked, corpus-tested, and verified in the installed wheel by
  `check_packaged_schemas` instead.
- **Record writes and temporaries.** A temporary is `.<target>.<16 hex>.tmp` beside its
  target and holds an exclusive `flock` while it lives, so the next write of the same
  target removes a crashed writer’s leftover without guessing from its age.
- **Lock files.** Each is created with `O_CREAT | O_EXCL` at its final path, so it is
  private from creation, and every acquisition opens its own descriptor.
  A lock file found shared is replaced by atomic rename only while holding its old lock
  taken without blocking, and refused if that lock is busy.
  The provider/resource lock lives at `cache/locks/providers/<key>.lock` until the
  provider storage plan names its spelling.
- **Layout adoption.** A cache with sources, stores, quarantine, or provider data but no
  `layout.yml` is refused rather than adopted or quarantined; leftover staging and trash
  do not block creating the first layout.
- **Store reclamation.** `reclaim_store` treats any entry under `provider-bindings/` or
  `provider-repositories/` as a reference until provider references are modeled, and
  treats an unreadable alias as a reference.
- **Records.** `RepositoryStoreState` carries `configuration_digest`, the store’s
  configuration snapshot, because the snapshot changes and `store.yml` is immutable;
  `object_state` is `complete` or `converging`, and `last_operation.kind` is `acquire`,
  `refresh`, or `converge`. Acquisition may extend these before `f01` ships.
- **Read routes.** `metabrowser.cache.routes` is the only cache module the server
  imports at startup; each handler loads `metabrowser.cache.projection`, and through it
  the application home, inside a cache request.
  Reads take no lock, because a lock file is a write and a cache hit must be readable
  from a home the process cannot write, so a concurrent move can show an entry mid-move.
  Directories are listed through `metabrowser.cache.listing`, which verifies the path
  the way a record read does and never creates it.
  A missing home is `absent`; entries under a future, unknown, or unmigrated layout, or
  under no layout, are refused exactly as `migrate_layout` refuses them.
  A read changes nothing it reads: every record read and every listing asks
  `metabrowser.home` for `shared="refuse"`, so an entry other users can reach is
  reported with publication `not_private`, kept apart from `damaged` because a record
  Metabrowser declined to read is not a corrupt one, or refused for a directory, naming
  the fixed layout location that failed and never a slug.
  A page holds at most 100 rows and defaults to 25; one request reads at most 400
  records, which the page rows and then the alias scan draw from, and a scan cut short
  reports its stores’ references as unknown rather than absent; a quarantine entry
  reports at most 50 names of each kind.
  Those follow the measured record-read costs recorded beside the constants and the fact
  that these projections run on the process-wide executor that also carries tree
  walking, rendering, raw sizing, and log tailing.
  One entry has one publication state on both source routes, because both build the row
  from all three of its records.
  The store’s `configuration_digest` is not reported.
- **Same-origin exposure of these routes is a content-trust dependency.** They are the
  first `/api` routes that answer with state from outside the served root, and an HTML
  file inside a browsed root runs same-origin, so once the cache holds entries such a
  file could fetch `/api/cache/sources` and read cached clone URLs and slugs.
  Nothing in Phase 1A populates the cache, so nothing is exposed yet.
  The sandboxed `/raw` and same-origin proof in `mb-cun0`, and the capability profile in
  `mb-vib1`, must be evaluated against a **populated** cache before Phase 1B-a lands and
  writes the first entries.

### Phase 1B: Generic Git cache and repository URL open

This phase lands in five additive slices.
Each can merge with its own records, routes, goldens, and recovery behavior before the
next slice begins.

#### Phase 1B-a: Acquire and reuse a shared repository store (`mb-h51g`, `mb-dg00`)

- [ ] Add conservative source normalization, and claim uniquified slugs under the
  source-alias lock with the identity digest, slug derivation, and collision extension
  Phase 1A added in `metabrowser.cache.identity` and `metabrowser.cache.locks`.
- [ ] Extend `git/process.py` with version detection, `stdin=DEVNULL`, non-interactive
  environment controls, and explicit acquisition/background policies.
- [ ] Enforce the acquisition floor from [Git version gates](#git-version-gates), which
  is also the lazy-fetch floor; select a full fetch before publication when the remote
  ignores the filter, and return a typed `unsupported_git_version` state below the
  floor.
- [ ] Acquire a worktree-free Git database in same-filesystem staging, resolve and pin
  the default full object ID, and validate records, objects, and refs.
  Publish the immutable store first; atomically create the source alias last as the
  visibility commit. Reclaim or quarantine a completed orphan store after interruption
  between the commits.
- [ ] Reuse a valid cache hit without network access, provider detection, or credential
  lookup, including against an application home the process cannot write.
- [ ] Prefetch the default revision’s tree blobs before publication, start object
  convergence only after serving, and persist honest partial, converging, complete, and
  failed states.
- [ ] Apply the Phase 0 lazy-fetch decision on every read path, and prove a
  not-yet-converged blob read behaves as decided both online and offline.
- [ ] Run those no-lazy-fetch acceptance tests against the lowest admitted Git release
  in CI, so the source reading behind the version floor is proven at runtime.
- [ ] Measure initial acquisition of a large or bitmap-less repository with a stalled or
  slow server, and choose its low-speed bound; until then user-driven job cancellation
  is the guard.
- [ ] Decide the distribution-backport policy recorded under
  [Git version gates](#git-version-gates).
- [ ] Replace the test oracle for the URL grammar, version gates, object requests, and
  the acquisition machine with the production functions, and replay the same fixtures.
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
- [ ] Persist a non-secret `StagedFetch` job record, take the store lease with no
  ordered lock held, verify the configuration snapshot, and fetch from a promisor remote
  recorded in it — never a URL — directly into the store under
  `refs/metabrowser/jobs/<job-id>/`; then validate object format, expected full OID,
  source, auth-context kind, refspec, and base generation, and publish with one
  `update-ref --stdin` compare-and-swap that deletes the job refs, under the short
  repository-store lock.
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
- [ ] Compact unreachable promisor objects that discarded or crashed fetch jobs left in
  blobless stores; `gc --prune=now`, `repack -a -d`, and `prune --expire=now` keep them.

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
  object IDs; source/auth-incompatible fetches do not coalesce; a slower fetch job
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
  summaries, bounded tree/blob reads, and diff rendering before and after convergence.
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

- Phase 0 selected blobless acquisition with default-revision prefetch and explicit
  convergence, and recorded the evidence it could not supply and who owns it, in
  [Phase 0 decisions](#phase-0-decisions).
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
  missing credential, unavailable network, and failed convergence each produce bounded
  and truthful outcomes;
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
