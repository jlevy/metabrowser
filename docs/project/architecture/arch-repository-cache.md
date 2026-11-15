# Repository Cache

**Status:** Built: the cache and configuration roots, the `f01` layout and its
migration, source and store identity, the SoftSchema record contracts, owner-only
storage, the lock hierarchy and side locks, the runtime probe, the startup sweep of
staging, and the read-only `/api/cache/` routes.
Planned: size accounting and a purge command for repository stores, which the
[thin-mirror plan](../specs/done/plan-2026-09-23-v012-thin-mirror.md) defers until after
the alpha.

The repository cache holds what Metabrowser keeps about a Git source it browses from a
URL: a worktree-free Git store for each repository, the records that name it, and the
records a provider plugin keeps beside it.
Everything in it can be rebuilt from its origin.
Clearing it loses offline reading and fetched metadata, never configuration.
How a store is filled and kept current is in
[Mirror Acquisition and Refresh](arch-mirror-acquisition-and-refresh.md); the GitHub
plugin’s records are in [GitHub Pull Requests](arch-github-pull-requests.md); what a
pinned revision serves is in
[Source Sessions and Pins](arch-source-sessions-and-pins.md).

## Cache and Configuration Directories

Cache and configuration have separate roots with separate lifecycles, following the
[uv storage](https://docs.astral.sh/uv/reference/storage/) convention.
`application_cache` and `configuration_directory` in `home.py` resolve them from a flag,
then an environment variable, then the XDG base directory, then the default; the
user-facing order is in [Storage locations](../../command-line.md#storage-locations).

- **Exact or base:** an application override names the exact directory; an XDG variable
  names a base, to which `metabrowser` is appended.
  An environment override must be a nonempty absolute path without `..` components, and
  a relative flag is anchored to the working directory.
- **No side effects:** resolution creates nothing.
  Browsing a local folder never resolves, imports, or initializes either root: the
  server imports only the cache route table at startup (`cache/routes.py`), and each
  handler imports the rest when it is requested.
- **No overlap:** `validate_storage_separation` refuses roots that overlap, through
  symlinked ancestors included, so deleting the cache cannot remove configuration.
- **Configuration is the user’s:** `config.yml` is created once by atomic create-only
  publication and is never rewritten by cache creation or migration.
  Unknown settings and comments survive, and a file that cannot be parsed is refused,
  never replaced. Its format version is independent of the cache’s.
- **No durable data:** a feature that needs state that cannot be rebuilt chooses a data
  directory of its own; it does not put it in the cache.

## Owner-Only Storage

Stores and provider records can hold private repository content, so `home.py` admits a
root only when no other principal can read it or redirect it.
Its module docstring states each rule and the threat it answers; in short:

- every directory above the root is owned by root or the current user and writable by no
  one else, and a symbolic link above it is followed only when root or the user owns it;
- the root and every entry below it have no group or other permissions and no ACL entry
  for another principal, and a regular file has one link;
- entries are reached by directory descriptor with `O_NOFOLLOW` and judged again on the
  opened descriptor, on every call;
- an entry the user owns that has become shared is tightened, with a warning, except
  where a caller must change nothing: the read routes ask for `shared="refuse"` and are
  refused instead; and
- a platform or file system that cannot show these facts is refused as unverifiable.

A refusal is a `PrivateStorageError`. Its message (`_describe` in `home.py`) names a
logical location and the remedy, such as running `chmod 700` on the root or choosing
another `METABROWSER_CACHE_DIR`, and never a path, because it can reach a job status or
an API envelope; the path stays on the exception for the CLI to print.
A malformed environment override and a layout from a newer release are refused with
remedies of their own.
A root other users can read refuses cache hits as well as new acquisitions.
A root the current user cannot write still serves cached sources, because reads take no
lock, and refuses only new ones.
`cli-cache-repair-guidance.txt` and `cli-cache-readonly-miss.txt` pin both.

## Layout

```text
<cache root>/
  CACHEDIR.TAG
  layout.yml
  locks/
    home.lock
    sources/<slug>.lock
    sources/<source key>.acquire.lock
    stores/<store key>.lock
    stores/<store key>.fetch.lock
    staging/<entry>.lock
  staging/<entry>/
  sources/<slug>/
    source.yml
    state.yml
    store-alias.yml
    pulls/                      provider records
  repository-stores/<store key>/
    repository.git/
    store.yml
    state.yml
    github-pull-manifests/      provider records
    github-pull-manifest-<slot>.epoch
```

`cache/paths.py` spells every record and directory location and `cache/locks.py` every
lock file, and their helpers refuse a slug, store key, or entry name that does not
validate rather than build a path from it.
A source directory says what was asked for and which store answers it; a store directory
holds the Git database and what is known about it.
A source with `source.yml` alone is `unattached`: the GitHub plugin publishes one for a
served checkout before any store exists.

`open_cache` in `cache/layout.py` prepares the root for use: it refuses a future format
before writing, creates or verifies the owner-only skeleton and `CACHEDIR.TAG`, runs the
[runtime probe](#runtime-probe), migrates the layout, and runs the
[startup sweep](#publication-and-deletion).
Acquisition, and the publication of an unattached source, call it; read routes never do.

`layout.yml` names the format of the whole root.
`cache/layout.py` owns the current format, the ordered history of formats a release has
written (`FORMAT_HISTORY`), and the migration from each to the next (`MIGRATIONS`).
Migration holds the home lock and publishes the layout after each step, so an
interrupted chain resumes where it stopped.
A newer format is refused with `FutureLayoutFormatError`, which asks for an upgrade.

## Identity

`cache/identity.py` holds the rules, frozen in
`tests/fixtures/repository-cache/source-identity.json` and replayed against it:

- **Source identity** is a SHA-256 digest of a domain, the transport, and the
  normalized, credential-free address the root-argument grammar produces.
  Transport is part of it, so an HTTPS and an SSH spelling are two sources unless a
  provider reducer maps both to one address.
- **Store identity** digests the source identity and the object format observed during
  acquisition, so two concurrent acquisitions of one source converge on one store.
  The **store key** is all of its hexadecimal digits.
- **Slug** is a readable lowercase prefix plus the shortest digest suffix no other
  source has claimed, recorded in `source.yml` at creation and never recomputed.

Spellings converge only through the grammar and the provider reducers.
The GitHub reducer lowercases owner and repository, so every spelling of a GitHub URL
shares one source, and a GitHub mirror is named in lowercase.
Two stores are never merged because their owner and name text match.

## Records

### Record Contracts

The records Metabrowser writes into the cache are enforced SoftSchema contracts.
`cache/contracts.py` binds each contract ID to one Pydantic model in `cache/records.py`
and one compiled Draft 2020-12 schema packaged under `data/cache-format/`, and
`plugin_loader/artifact_contracts.py` validates every record on read and on write.
A cache file names its contract, envelope, and status but never a schema path: the
caller chooses the contract from the file’s place in the layout, so cached data cannot
select the schema that validates it.
Identity and mutable state are separate records: `source.yml` and `store.yml` say what
an entry is, `store-alias.yml` is the generation-checked attachment of a source to a
store, and each `state.yml` holds what changes.
The registry is internal; nothing outside this package declares a contract.

`devtools/check_artifact_contracts.py` compares this table with the installed
declarations and runs each contract’s schema, semantic validator, positive and negative
conformance corpus, and deterministic round trip; the distribution check runs the same
inventory against isolated wheel and source installs.
`config.yml` is user-owned and validated permissively, so it is not in the table;
`check_packaged_schemas` compiles it with the others.

| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus |
| --- | --- | --- | --- | --- | --- |
| `metabrowser.cache:CacheLayout/v1` | `pure-yaml` | `layout` | `repository-cache` | `repository-cache` | `cache-records-conformance[layout]` |
| `metabrowser.cache:RepositorySource/v1` | `pure-yaml` | `source` | `repository-cache` | `repository-cache` | `cache-records-conformance[source,scp_source]` |
| `metabrowser.cache:RepositorySourceState/v1` | `pure-yaml` | `state` | `repository-cache` | `repository-cache` | `cache-records-conformance[source_state]` |
| `metabrowser.cache:RepositoryStore/v1` | `pure-yaml` | `store` | `repository-cache` | `repository-cache` | `cache-records-conformance[store]` |
| `metabrowser.cache:RepositoryStoreAlias/v1` | `pure-yaml` | `alias` | `repository-cache` | `repository-cache` | `cache-records-conformance[store_alias]` |
| `metabrowser.cache:RepositoryStoreState/v1` | `pure-yaml` | `state` | `repository-cache` | `repository-cache` | `cache-records-conformance[store_state,empty_store_state]` |

`cache/atomic.py` reads a record through `open_private_file` with a size bound
(`MAX_RECORD_BYTES`) and writes it only through `write_private_file_atomic`, so an
interrupted write leaves the previous record.

### Provider Records

The files under `sources/<slug>/pulls/` and a store’s `github-pull-manifests/` belong to
the GitHub plugin and are not SoftSchema contracts.
Nothing in the cache enumerates them, so the layout, probe, sweep, and `/api/cache/`
projections leave them alone.
[GitHub Pull Requests](arch-github-pull-requests.md#files-beside-a-source) lists them
and how each is written.

## Repository Stores

A store is a bare repository, created with an empty template and configuration written
only by Metabrowser, with `gc.auto=0` and `maintenance.auto=false`, by Git running under
umask `077`. These invariants hold for every store:

- there is no index, no checked-out branch, and no view operation runs `checkout`,
  `switch`, `reset`, or `worktree add`;
- its refs are the origin’s branches under `refs/remotes/origin/`, its tags, and the
  `refs/pull/<n>/head` of each pull request fetched into it; Metabrowser writes no ref
  of its own, and deletes one only in an overlay’s sweep of refs whose objects the
  lender collected;
- no operation runs `gc`, `prune`, or `repack`, so a commit in a store stays readable
  and a reader needs no lock; and
- a **full** store holds every object it fetched, while an **overlay** store borrows a
  named checkout’s objects through `objects/info/alternates` and holds what that lacks
  ([The Lending Checkout](arch-mirror-acquisition-and-refresh.md#the-lending-checkout)).

`open_revision` in `cache/repository_store.py` proves a commit is in a published store
and returns its `GitRevisionSubject`, writing nothing and holding no lock.
Every store read runs under `STORE_READ_POLICY` in `git/process.py`, which isolates the
user’s configuration and attributes, takes attributes from the store’s empty tree, and
sets `GIT_NO_LAZY_FETCH=1`, though a store has no promisor remote; and with
`GIT_DISABLE_MAILMAP_ARGS`, because a bare store’s default mailmap is `HEAD:.mailmap`.
Git can report a failed read on stderr and still exit 0, so stderr from a store read
degrades the result.
A store’s configuration names no diff driver, and a borrowed checkout’s configuration is
never read, which is one reason a checkout’s objects are read only through a store.
The pool of batch readers per store (`MAX_BATCH_READERS_PER_STORE` in
`git/tree_source.py`) is part of the tree source.

A complete object read verifies the object ID against the header and bytes in the
store’s SHA-1 or SHA-256 format, and a mismatch is `object_corrupt`. A windowed read
hashes only when the drain consumes the whole object, so a large preview makes no claim
of authentication. A read that fails is recorded in `git/object_failures.py`, a bounded
memory of observed object IDs per store and commit selection, which only an explicit
[recovery](arch-mirror-acquisition-and-refresh.md#object-recovery) consults.

## Locks

Locks are BSD `flock` on files under `locks/`, never POSIX record locks, which vanish
when a process closes any descriptor of the file.
`cache/locks.py` holds the hierarchy:

1. the application-home lock, for layout migration and brief global enumeration;
2. source-alias locks, in ascending slug order; and
3. repository-store locks, in ascending store-key order.

A thread takes hierarchy locks in ascending rank and key and never takes one twice;
`LockOrder` refuses anything else before a descriptor is opened.
Network work and long-running Git first call `require_no_hierarchy_locks`.

Side locks sit outside the order and are only tried without blocking:

- a **staging entry** lock marks one owner’s liveness;
- a **source acquisition** lock reserves a cold miss through publication, and other
  openers of that source wait for it and then look for the published store; and
- a store’s **fetch** lock marks the one fetch into it.
  Git processes that write the store inherit its descriptor, so it stays held while any
  of them runs, even after the process that took it has died.

Every acquisition is its own `open()` of the lock file, and descriptors are never shared
or duplicated, because `flock` state belongs to the open file description and a request
through a duplicate is granted rather than refused.
No lock blocks a thread that runs an event loop (`_acquire` refuses it); blocking
sections run in worker threads through `run_lock_section`. No lock protects a reader.
A lock file found shared with another principal is replaced only while its old lock is
held.

`tests/fixtures/repository-cache/state-machines.json` freezes the hierarchy, the side
locks, the lock sequences, and the startup sweep’s machine.
`tests/test_repository_cache_contract_fixtures.py` replays the sequences through
`cache/locks.py`, and `tests/test_cache_reclaim.py` checks every transition the real
sweep reports, with the locks it holds, against the machine.

## Runtime Probe

The lock and publication rules were measured on one macOS APFS volume, and a network
file system can emulate `flock` with record locks.
So before the cache uses a root, `cache/probe.py` checks on that root that another
process cannot take a held lock, that closing an unrelated descriptor keeps the lock,
that a second `open()` in one process contends, and that no-replace publication refuses
an existing target. A root that fails is refused as unverifiable.
The result is kept for the life of the process, keyed by the device and inode of
`locks/`.

## Publication and Deletion

Publication renames a staged directory or file to a path that must not exist, while
holding the lock every writer of that path takes, using the platform’s no-replace rename
(`renameat2(RENAME_NOREPLACE)` or `renamex_np(RENAME_EXCL)`) where there is one
(`cache/atomic.py`). A store is published before its source alias, and the alias is the
only visibility commit; acquisition holds the alias lock and then the store lock from
the store’s rename through the alias write, which `tests/test_cache_publish.py` checks.

Nothing deletes or moves a published store or source.
A store that no alias names, which a crash between the two renames leaves, stays until
the next acquisition of its source reuses it (`cli-cache-orphan-kept.txt`). The only
deletion is the startup sweep in `cache/reclaim.py`: under the home lock it lists the
staging entries, releases the lock, and deletes each entry whose liveness lock is free,
along with lock files whose entry is gone.
Liveness is the lock, never age, since no age tells a slow clone from a dead one.
The GitHub plugin removes its own records on request
([cache-clear](arch-github-pull-requests.md#clearing-the-cache)).

## Read-Only Cache Routes

`/api/cache/layout`, `/api/cache/sources`, `/api/cache/source/<slug>`, and
`/api/cache/stores` make the cache inspectable through `metab --api`, so it needs no
inspection command of its own.
`cache/projection.py` builds them:

- each request resolves the roots and never creates them; a missing root is `absent`;
- reads take no lock and ask for `shared="refuse"`, so a cache hit answers from a root
  the process cannot write and nothing is tightened to answer a request;
- a format the release would refuse is refused the same way, as a typed, path-free
  `CacheError`, and a damaged entry is listed beside the readable ones with its reason;
- enumeration and record reads are bounded (`MAX_DIRECTORY_ENTRIES`,
  `MAX_RECORDS_PER_REQUEST`, `MAX_PAGE_LIMIT`), and pages run in key order; and
- no answer names a cache path, a pack file, a Git internal, or the root itself
  (`cache/wire.py`). A store reports its `mode`, `full` or `overlay`, and its `lender`,
  `present` or `lender_missing`.

A server serving a pinned revision answers every one of them with
`unsupported_for_subject`, so nothing about other cached sources is served beside
untrusted content; `metab <url> --api /api/cache/…` inspects the cache instead.
`tests/test_cache_routes.py` and `cli-api-cache.tryscript.md` pin them.

## Measured Choices

Phase 0 measured the store’s layout, its Git configuration, its locks, and its readers
on 2026-09-16; the comment beside each choice gives its measurement, and
[Repository cache measurements](../../../explorations/repository-cache/README.md) has
the method and figures, with the open-repo plan’s
[Phase 0 decisions](../specs/active/plan-2026-08-11-open-repo-from-git-url.md#phase-0-decisions)
listing those still open.
These choices may change cost.
They may not add shared working-tree state, make a checkout the cache’s authority, or
weaken immutable publication.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
