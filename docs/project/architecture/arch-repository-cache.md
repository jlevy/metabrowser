# Repository Cache

**Status:** Built: the cache and configuration roots, the `f03` layout and its
migrations from `f01` and `f02`, source and store identity, the SoftSchema record
contracts, owner-only storage, the lock hierarchy and side locks, the runtime probe, the
startup sweep of staging, and the read-only `/api/cache/` routes.
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
  Browsing a local folder never resolves, imports, or initializes the cache, and reads
  no `config.yml`: the server imports only the cache route table at startup
  (`cache/routes.py`), and each handler imports the rest when it is requested.
  Serving a folder writes one file in the configuration directory, its entry among the
  [recent targets](arch-recent-targets.md), through `home.py` alone;
  `test_local_browsing_in_process_never_calls_the_application_cache` holds both.
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
    sources/<source digest>.acquire.lock
    stores/<store key>.lock
    stores/<store key>.fetch.lock
    staging/<entry>.lock
    providers/                  provider locks
  staging/<entry>/
  sources/<slug>/               one per repository address
    source.yml
    state.yml
    store-alias.yml
    pulls/                      provider records
  repos/<store key>/            one per Git database
    repository.git/
    store.yml
    state.yml
    github-pull-manifests/      provider records
    change-sizes/               measured change sizes
    github-pull-manifest-<slot>.epoch
  plugins/<plugin>/             a plugin's own cache, which Metabrowser never reads
```

A **source** is a repository as addressed and what its provider said about it; a
**repo** is Metabrowser’s own Git copy of it and what was computed from that copy.
Both directories hold one entry per repository, and `repos/` is named for what is in it:
a bare repository, whether it is opened as a mirror or attached beside a served checkout
for pull request comparisons.
`repository.git` is the name of that bare repository, which `git -C` takes, and
`store_git_directory` in `cache/paths.py` spells its path.
Lock files for stores stay under `locks/stores/`, where the code’s word “store” is kept,
and renaming a directory of locks while a process may hold one is the one unsafe rename.

`cache/paths.py` spells every record and directory location, including the Git directory
of a store, and `cache/locks.py` every lock file, and their helpers refuse a slug, store
key, or entry name that does not validate rather than build a path from it.
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

`f02` is the format in which a store directory is named by a key and not by the whole
digest of its identity, as `f01` named it.
`f03` is the format of the names as they now read, for both entries: single-dash words
and a base-36 suffix ([store keys](#store-keys) and [slugs](#slugs)), where `f02` joined
its words with `--` and spelled the suffix in hexadecimal; and the stores live in
`repos/`, where `f01` and `f02` kept them in `repository-stores/`.
`cache/store_rename.py` migrates a home from either to `f03`, which `acquire_source`
does before it looks for a hit, so a store cached by an older release is still a hit,
and no clone is repeated.
A home that is `f01` is renamed once, straight to its `f03` names, and the step from
`f02` that follows finds nothing left to rename.
Each entry is renamed where it stands, and a store is moved into `repos/` by the same
atomic, no-replace rename that respells its key; the skeleton has made `repos/` already,
so the parent is not renamed in one step.
Sources go first: `source.yml` records its slug and validates it against the identity,
so its record is rewritten with the new slug in the old directory, and the directory is
renamed after, which leaves an interrupted migration an entry under its old name to
finish and never a directory whose record disagrees with its name.
A rename was chosen over leaving the old names because a store can hold a repository of
gigabytes and nothing in the cache deletes one: orphaned, every store would be cloned
again and the old copies would stay, listed by nothing.
The renames are planned first and applied by `apply_renames`, which takes paths relative
to the home and moves each entry to the first target nothing holds, so a later step that
moves other directories is another plan and not another mechanism.
The repository a store holds is read from the source whose alias names it, or whose
identity derives it in either object format, so a store that an interrupted acquisition
left unreferenced keeps its repository’s name, and the next acquisition of that source
reuses it. A store no source names keeps the words an `f02` name had, and an `f01` one,
which had none, takes the readable part `unattached`, so it is listed as unreferenced
and kept, as it always was.
A directory whose `store.yml` or `source.yml` does not record the identity its name
spells was damaged already and is left as it is, and an entry the migration cannot read,
such as a record with a second hard link or a file where a store belongs, is named in a
warning and skipped, so that one entry cannot stop every open.
A skipped or damaged store is moved into `repos/` under the name it had, with the other
entries no route recognises, and the old parent is removed once it is empty; a source
left under its old name stays in `sources/`, listed among its unrecognised entries.

The migration is the first write to the home after an upgrade, so that first open needs
a writable cache, and a home read before it answers `migration_pending`, which says that
opening any repository with `metab` migrates the cache.
The macOS app reads `/api/cache/sources` to know whether a repository is cached and
takes `migration_pending` for “not cached”, so it asks its clone question once for a
repository it already holds.

Migrating while a process of the older release runs is unsupported, and the changelog
says to stop them first (the app restarts its own).
Such a process refuses the migrated home as a newer format when it next opens the cache,
and fails to read its mirrors until it is restarted, since the directories it reads have
moved. One that has a clone in flight publishes its store under its old name after the
migration, and its alias then names a store that no key holds.
That is a miss and not damage: the next open fetches the repository again, publishes it
under its key, and leaves the alias as it is, where `_find_published` used to refuse
every open of it with “the aliased store is missing”.
`/api/cache/sources` lists such a source `dangling` until then, and the directory under
the old name stays, counted among the stores route’s unrecognized entries.
Renaming it to the key its store would have been given, before that open, keeps the
clone; clearing the cache removes it.

## Identity

`cache/identity.py` holds the rules, frozen in
`tests/fixtures/repository-cache/source-identity.json` and replayed against it:

- **Source identity** is a SHA-256 digest of a domain, the transport, and the
  normalized, credential-free address the root-argument grammar produces.
  Transport is part of it, so an HTTPS and an SSH spelling are two sources unless a
  provider reducer maps both to one address.
- **Store identity** digests the source identity and the object format observed during
  acquisition, so two concurrent acquisitions of one source converge on one store.
  The **store key** is the name of its directory; see [Store Keys](#store-keys).
- **Slug** is the name of a source’s directory, of one grammar with a store key; see
  [Slugs](#slugs). It is recorded in `source.yml` at creation and never recomputed.

Spellings converge only through the grammar and the provider reducers.
The GitHub reducer lowercases owner and repository, so every spelling of a GitHub URL
shares one source, and a GitHub mirror is named in lowercase.
Two stores are never merged because their owner and name text match.

### Store Keys

A store directory is named `<readable>-<suffix>`, such as
`github-com-jlevy-markform-1bo2sp3ey2l`, where it was once
`github-com--jlevy--markform--096a832ec2dfe765`, and before that the whole digest of the
store identity. The readable part is the words of the repository’s address, joined by
single dashes, and the suffix is the first `NAME_SUFFIX_CHARS[0]` base-36 characters
(`0-9a-z`) of the identity’s digest, read as a fraction of 1 so that a longer suffix
begins with a shorter one and a leading zero is kept.
So the key is a name and the identity is the record: `store.yml` holds the whole `id`,
and a lookup or a listing checks it.

- **The width is sized, and never relied on.** `NAME_SUFFIX_CHARS` in
  `cache/identity.py` carries the birthday-bound arithmetic that picked the first width,
  and `tests/test_cache_store_keys.py` recomputes it.
  Two stores can take one first name only when they agree on that many bits of digest
  and on the readable part, and the sizing does not even count the readable part.
- **The suffix is the last token, whatever the words before it look like.** A repository
  named like a suffix, `abcdefghijk`, gives `github-com-jlevy-abcdefghijk-<suffix>`, and
  the suffix is what follows the last dash.
  A name of the right shape is not thereby a store’s: only a suffix of the identity
  `store.yml` records ties a name to a store (`store_key_matches_identity`), and an
  `f02` name with its `--` or an `f01` whole digest is no key at all.
- **A name another store holds is never shared.** The claim reads the identity recorded
  at each candidate, takes the first no other store holds, and does it under the store’s
  lock (`_claim_store_key` in `cache/acquire.py`). A lookup finds the store at the
  candidate that records its identity, however far down the list it is, so a store that
  took a longer name is not published twice when the shorter one is freed.
  Beating the odds therefore costs a longer name and nothing else, and
  `tests/test_cache_acquire.py` forces it.
- **A directory with no readable `store.yml` is damage and not a free name.** A claim
  never publishes beside it, and a lookup refuses it instead of reading it as another
  store’s.
- **A source’s reservation keeps the whole digest.** `locks/stores/<key>.lock` takes the
  key, but `locks/sources/<source digest>.acquire.lock` reserves a source’s cold load
  before any slug exists.
  Only the message of a wait that timed out shows it.

### Slugs

A source directory is named for the repository in the same way, with its source
identity: `sources/github-com-jlevy-markform-jqlzm24hgct`, where `f02` had
`github-com--jlevy--markform--8c5e18ed6f7f`. A slug and a store key have one grammar
(`is_slug` and `is_store_key`), and `slug_matches_identity` and
`store_key_matches_identity` tell them apart by the identity each suffix digests, so a
name is a slug only of the source whose identity it ends in.
`source.yml` records the slug, and `RepositorySource` refuses a record whose slug is not
one of its identity’s, so the record, its packaged schema, and the directory move
together.
A source is claimed under the source-alias lock (`cache_slug`), takes the first
slug no other source holds, and is never renamed once published.
The same sizing holds as for stores, since the cache routes list at most the same number
of sources, and the same widths: 11, 19, 25, then 50 characters.

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
A record republished while a read opens it is refused as replaced, and the read opens it
again, judging the new record in full, up to `MAX_READ_OPENS` times, so it reads the old
record or the new.

### Atomic Writes

`write_private_file_atomic` in `home.py` writes every record and provider file.
The bytes go to a temporary file beside the target, named by `_TEMPORARY_SUFFIX_RE` and
created exclusively with mode `PRIVATE_FILE_MODE`, which is flushed, renamed into place,
and its directory synced.
Each temporary holds an exclusive `flock` for its whole life, so the next writer of the
target removes a crashed writer’s leftover, whose lock is free, and leaves a live one.
A write that fails once its temporary is held removes the temporary while still holding
it.

A file exists before it can be locked, and a sweep that ran between the two once removed
a live writer’s new temporary, whose write was then refused as replaced.
So a writer holds a shared `flock` on the directory, through a description of its own,
from before it creates its temporary until it has locked it.
A sweep judges the other temporaries only while it holds that lock exclusively: it tries
the lock without blocking and leaves the leftovers to a later write if a writer is
creating one. A sweep holds it only while it opens, tries, and removes the other
temporaries of its target, which wait on nothing but the warning logged if a swept file
must be tightened first; it logs its removals after releasing the lock.
A writer retries the shared lock without blocking up to `_TEMPORARIES_LOCK_WAIT_S`,
whose comment gives the measured holds, and then goes ahead without it, so a stopped or
stalled holder costs each write that bound rather than stopping it.
Both release the lock with `LOCK_UN`, so a child forked meanwhile does not keep it.
Where the file system cannot lock a directory (`_DIRECTORY_LOCK_UNSUPPORTED_ERRNOS`),
writers go ahead without it and sweeps skip.
`tests/test_cache_atomic.py` runs a second writer inside the first writer’s window,
holds the directory lock against a writer, and contends writers in threads and in
processes.

### Provider Records

The files under `sources/<slug>/pulls/`, a store’s `github-pull-manifests/`, and its
`github-pull-manifest-<slot>.epoch` files belong to the GitHub plugin and are not
SoftSchema contracts.
Nothing in the cache enumerates them, so the layout, probe, sweep, and `/api/cache/`
projections leave them alone.
[GitHub Pull Requests](arch-github-pull-requests.md#files-beside-a-source) lists them
and how each is written.

A store’s `change-sizes/` holds the sizes of changes measured in it, by the head
commit’s first two hexadecimal digits, one file each
([Change Sizes](arch-git.md#change-sizes)). It is not a SoftSchema contract either: a
file that cannot be read, was written for other measuring options, or does not validate
is a miss, measured again; each file is bounded by `MAX_BANK_FILE_BYTES` and
`MAX_BANK_FILE_ENTRIES` in `git/change_size.py`.

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
A store’s configuration names no diff driver, and a checkout that lends its objects to a
store never has its configuration read, which is one reason a mirror reads a checkout’s
objects only through its own store.
A folder’s server is the other case: it reads its own checkout’s Git directory in place,
for history and for that checkout’s revisions, with the checkout’s local configuration
in effect, so those reads pass the options that keep a configured program from running
([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)).
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
A store row carries its `key`, the directory name below `repository-stores`, which is
also what a page continues after, and the `id` its `store.yml` records, which is `null`
when that record cannot be read.
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
